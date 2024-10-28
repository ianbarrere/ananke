#!/usr/bin/env python3
"""
CLI adapter for device interaction
"""
import json
import click  # type: ignore
import logging
from click_option_group import optgroup, MutuallyExclusiveOptionGroup  # type: ignore
from ananke.connectors.shared import WRITE_METHODS
from ananke.struct.dispatch import Dispatch
from typing import Tuple, Literal, Any
from colorama import Fore, Style
from time import sleep


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
    "-S",
    "--skip-defaults",
    "skip_defaults",
    is_flag=True,
    default=False,
    help="Skip default configs (if supported in transform)",
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
    skip_defaults: bool,
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
    deploy_tags = []
    if dry_run:
        deploy_tags.append("dry-run")
    if skip_defaults:
        deploy_tags.append("skip-default")
    dispatch = Dispatch(targets=targets, deploy_tags=deploy_tags)
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
