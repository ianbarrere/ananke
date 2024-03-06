#!/usr/bin/env python3
"""
CLI adapter for device interaction
"""
import click  # type: ignore
from click_option_group import optgroup, MutuallyExclusiveOptionGroup  # type: ignore
from ananke.connectors.shared import WRITE_METHODS
from ananke.struct.config import Config
from ananke.struct.dispatch import Dispatch
from typing import Tuple, Literal


main = click.Group(help="Device configurator")


@main.command(name="set")
@click.argument("target_type", type=click.Choice(["device", "service"]))
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
    target_type: Literal["device", "service"],
    targets: Tuple[str],
    sections: str,
    method: WRITE_METHODS,
    debug: bool,
    dry_run: bool,
) -> None:
    """
    Push config to devices/services. Specify comma-separated list of hosts, roles,
    and/or services with an optional config section parameter
    """
    if method not in [None, "replace", "update"]:
        raise ValueError("Method must be replace or update")
    # allow to run with targets from environment variable
    if len(targets) == 1 and " " in targets[0]:
        targets = targets[0].split(" ")
    dispatch = Dispatch(target_type=target_type, targets=targets)
    for target_device in dispatch.targets:
        config = Config(
            target_id=target_device.id,
            sections=sections,
            settings=dispatch.settings,
            variables=target_device.variables,
        )
        target = target_device.connector(
            target_id=target_device.id,
            username=target_device.username,
            password=target_device.password,
            settings=dispatch.settings,
            variables=target_device.variables,
        )
        body, output = target.deploy(method, config.packs, dry_run=dry_run)
        if not body and not output:
            click.secho(
                f"Config set disabled for {target.target_id}, skipping", fg="yellow"
            )
            continue
        if debug or dry_run:
            if output:
                click.secho(output, fg="magenta")
            click.secho(body, fg="white")
            continue
        click.secho(f"Config section(s) pushed to {target.target_id}", fg="cyan")


@main.command(name="get")
@click.argument("hostname")
@click.argument("path")
@click.option("-O", "--oneline", "oneline", is_flag=True, default=False)
@click.option("-o", "--operational", "operational", is_flag=True, default=False)
def gnmi_get(hostname: str, path: str, oneline: bool, operational: bool) -> None:
    """
    Get config from device based on gNMI path
    """
    dispatch = Dispatch([hostname], target_type="device")
    for device in dispatch.targets:
        connection = device.connector(
            target_id=device.id,
            username=device.username,
            password=device.password,
            settings=dispatch.settings,
            variables=device.variables,
        )
        config = connection.get_config(
            path=path, oneline=oneline, operational=operational
        )
        click.secho(config, fg="white")


if __name__ == "__main__":
    main()
