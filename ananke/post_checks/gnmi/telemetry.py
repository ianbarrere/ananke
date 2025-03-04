#!/usr/bin/env python3
from pygnmi import client  # type: ignore
from typing import List, Any, Generator


def subscribe(target_dict: Any, paths: List[str]) -> Generator[Any, Any, Any]:
    """
    Given a hostname and a list of paths, subscribe to the paths for polling
    telemetry data
    """
    subscription_def = {
        "subscription": [
            {
                "path": path,
                "mode": "sample",
            }
            for path in paths
        ],
        "mode": "poll",
    }
    with client.gNMIclient(**target_dict) as session:
        subscription = session.subscribe2(subscribe=subscription_def)
        yield subscription.get_update(timeout=20)
