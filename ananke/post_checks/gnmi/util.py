#!/usr/bin/env python3
import yaml  # type: ignore
import os
from pygnmi import client  # type: ignore
from typing import List, Any
from ananke.struct.vault import Vault


def get_gnmi_val(container: Any) -> List[Any]:
    """
    NX-OS sometimes returns object['val'] as a list and other platforms don't, there
    never seems to be any more than 1 entry in the val list though so we just return
    the first element
    """
    if isinstance(container, list):
        return container[0]
    return container


def get_gnmi_session(
    hostname: str, username: str, password: str, port: int
) -> client.gNMIclient:
    """
    Establish and return a session with pygnmi client
    """
    with open(os.environ["ANANKE_CONFIG"] + "/settings.yaml", "r") as settings_file:
        settings = yaml.safe_load(settings_file)
    domain_name = settings["domain-name"]
    if domain_name not in hostname:
        hostname = hostname + "." + domain_name
    target_dict = {
        "target": (hostname, port if port else 57777),
        "username": username,
        "password": password,
        "path_cert": settings["certificate"]["directory"]
        + settings["certificate"]["name"],
    }
    return client.gNMIclient(**target_dict)
