#!/usr/bin/env python3
"""
CLI adapter for device interaction
"""
import json
import click  # type: ignore
import logging
import os
from typing import Tuple, Any
from colorama import Fore, Style
from time import sleep
from click_option_group import optgroup, MutuallyExclusiveOptionGroup  # type: ignore
from ananke.connectors.shared import WRITE_METHODS
from ananke.struct.dispatch import Dispatch
from ananke.post_checks.slack import post_run_check_notification


main = click.Group(help="Device configurator")

logger = logging.getLogger(__name__)


def color_results(prefix: str, message: str, message_color: Any) -> str:
    return (
        Fore.WHITE
        + Style.DIM
        + f"{prefix}: "
        + Style.RESET_ALL
        + message_color
        + message
    )


@main.command(name="set")
@click.argument("targets", nargs=-1)
@click.option(
    "-s",
    "--section",
    "sections",
    help="Config section to push",
    type=str,
    default=None,
    multiple=True,
)
@click.option(
    "-m",
    "--method",
    "method",
    help="Method for write operations, default is replace",
    default=None,
)
@click.option(
    "-C",
    "--post-checks",
    "post_checks",
    type=int,
    default=0,
    help="Number of post checks to run, default is 0",
)
@click.option(
    "-I",
    "--post-check-interval",
    "post_check_interval",
    type=int,
    help="Interval in seconds between post checks, default is 60",
)
@click.option(
    "-T",
    "--diff-tolerance",
    "diff_tolerance",
    type=int,
    help="Variation tolerance percentage for integers in post check diffs, default is 10",
)
@click.option(
    "-S",
    "--slack-post-checks",
    "slack_post_checks",
    is_flag=True,
    type=bool,
    help="Send post check results to slack",
)
@optgroup.group(
    "Dry-run or debug",
    cls=MutuallyExclusiveOptionGroup,
    help="Dry-run or debug",
)
@optgroup.option(
    "-d",
    "--debug",
    "debug",
    is_flag=True,
    default=False,
    help="Print JSON body and return message to terminal",
)
@optgroup.option(
    "-D",
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="",
)
def config_set(
    targets: Tuple[str],
    sections: str,
    method: WRITE_METHODS,
    debug: bool,
    dry_run: bool,
    post_checks: int,
    post_check_interval: int,
    diff_tolerance: int,
    slack_post_checks: bool,
) -> None:
    """
    Push config to devices. Specify comma-separated list of hosts and/or roles with an
    optional config section parameter
    """
    if method not in [None, "replace", "update"]:
        raise ValueError("Method must be replace or update")
    # allow to run with targets from environment variable
    if len(targets) == 1 and " " in targets[0]:
        targets = targets[0].split(" ")
    targets = (
        {target: set(sections) for target in targets}
        if targets
        else {None: set(sections)}
    )
    if (post_check_interval or diff_tolerance) and not post_checks:
        raise ValueError(
            "Post check interval/tolerance specified without number of post checks"
        )
    deploy_tags = []
    if dry_run:
        deploy_tags.append("dry-run")
    dispatch = Dispatch(
        targets=targets,
        deploy_tags=deploy_tags,
        post_checks=True if post_checks else False,
    )
    dispatch.concurrent_deploy(method)
    retry = 1000
    wait_time = 0.2
    total = retry * wait_time
    while len(dispatch.deploy_results) != len(dispatch.targets) and retry > 0:
        print(dispatch.deploy_results)
        sleep(wait_time)
        retry -= 1
    if len(dispatch.deploy_results) != len(dispatch.targets):
        message = "Deploy did not complete after {} seconds\nDeploy results: {}".format(
            total, dispatch.deploy_results
        )
        logger.error(message)
        raise RuntimeError(message)
    fg_translate = {1: Fore.RED, 2: Fore.YELLOW, 3: Fore.WHITE}
    for result in dispatch.deploy_results:
        click.echo(color_results("target", result.source, Fore.CYAN))
        if dry_run or debug:
            click.echo(
                color_results("config", json.dumps(result.body, indent=2), Fore.WHITE)
            )
        if debug:
            click.echo(
                color_results(
                    "device response", json.dumps(result.output, indent=2), Fore.MAGENTA
                )
            )
            for message in result.messages:
                click.echo(
                    color_results(
                        "message", message.text, fg_translate[message.priority]
                    )
                )
        else:
            min_priority = min([message.priority for message in result.messages])
            message = "Config section(s) pushed to device"
            if min_priority == 1:
                message = "One or more config sections failed"
            elif min_priority in [2, 3]:
                message = result.messages[0].text
            click.echo(color_results("message", message, fg_translate[min_priority]))
    if post_checks:
        click.secho("Running post checks...", fg="yellow")
        post_check_interval = post_check_interval or 10
        diff_tolerance = diff_tolerance or 10
        sleep(post_check_interval)
        check_results = []
        for check_number in range(post_checks):
            dispatch.post_status.poll(tolerance=diff_tolerance)
            check_results.append(dispatch.post_status.results)
            click.secho(
                "Post check {}/{}".format(check_number + 1, post_checks), fg="cyan"
            )
            for host, diffs in check_results[-1].items():
                click.secho("  " + host + ": ", fg="magenta")
                if diffs:
                    for diff in diffs:
                        click.secho(f"    - {diff}", fg="white")
                else:
                    click.secho("    " + "\U00002705", nl=False)
                    click.secho(" No diffs", fg="green")
            slack_webhook = dispatch.settings["post-checks"].get("slack-webhook")
            if "ANANKE_SLACK_WEBHOOK" in os.environ:
                slack_webhook = os.environ["ANANKE_SLACK_WEBHOOK"]
            if slack_webhook and slack_post_checks:
                post_run_check_notification(
                    check_results,
                    check_number,
                    post_checks,
                    slack_webhook,
                )
            if check_number < post_checks - 1:
                sleep(post_check_interval)


@main.command(name="get")
@click.argument("hostname")
@click.argument("path")
@click.option("-O", "--oneline", "oneline", is_flag=True, default=False)
@click.option("-o", "--operational", "operational", is_flag=True, default=False)
def gnmi_get(hostname: str, path: str, oneline: bool, operational: bool) -> None:
    """
    Get config from device based on gNMI path
    """
    target = {hostname: set()}
    dispatch = Dispatch(targets=target)

    target = dispatch.targets[0]
    connection = target.connector
    config = connection.get_config(path=path, oneline=oneline, operational=operational)
    click.secho(config, fg="white")


if __name__ == "__main__":
    main()
