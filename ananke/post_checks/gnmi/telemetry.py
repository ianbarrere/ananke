#!/usr/bin/env python3
from ananke.post_checks.gnmi.util import get_gnmi_session
from typing import List, Any, Generator


def subscribe(
    hostname: str, paths: List[str], username: str, password: str, port: int
) -> Generator[Any, Any, Any]:
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
        "encoding": "json_ietf" if "edge" in hostname else "json",
    }
    with get_gnmi_session(hostname, username, password, port) as session:
        subscription = session.subscribe2(subscribe=subscription_def)
        yield subscription.get_update(timeout=20)
