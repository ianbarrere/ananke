import requests
from typing import Any, Dict, List


def post_run_check_notification(
    results_list: List[Dict[str, List[Any]]],
    check_number: int,
    total_checks: int,
    slack_webhook: str,
) -> None:
    """
    Sends results of Ananke post run check to slack
    """

    def _get_message_emoji(path_diffs: List[Any]) -> bool:
        """
        Return relevant emoji for diff list
        """
        if not isinstance(path_diffs, list):
            return ":information_source:"
        last = [(path_diff[-2], path_diff[-1]) for path_diff in path_diffs]
        if ("oper-status", ("UP", "DOWN")) in last or (
            "session-status",
            ("UP", "DOWN"),
        ) in last:
            return ":warning:"
        elif ("oper-status", ("DOWN", "UP")) in last or (
            "session-status",
            ("DOWN", "UP"),
        ) in last:
            return ":up:"
        return ":information_source:"

    body = {"blocks": []}
    check_results = results_list[check_number]
    check_number += 1
    if check_number == 1:
        header = ":test_tube: " f"*Ananke CLI post change report*\n"
        body["blocks"].append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": header},
            }
        )
    body["blocks"].append(
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Check {check_number}/{total_checks}"},
            ],
        }
    )
    no_diff_hosts = [hostname for hostname, diffs in check_results.items() if not diffs]
    for hostname, changed_paths in check_results.items():
        if hostname not in no_diff_hosts:
            if (
                check_number > 1
                and changed_paths == results_list[check_number - 2][hostname]
            ):
                body["blocks"].append(
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f":router:\t_{hostname}_\tNo change since previous check\t:arrow_up:",
                            },
                        ],
                    },
                )
            else:
                body["blocks"].extend(
                    [
                        {
                            "type": "context",
                            "elements": [
                                {"type": "mrkdwn", "text": f":router:\t_{hostname}_"},
                            ],
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "\n".join(
                                        [
                                            f"{_get_message_emoji(path_diffs[1])}\t*Path:* "
                                            f"{path_diffs[0]} *Diffs:* {path_diffs[1]}"
                                            for path_diffs in changed_paths
                                        ]
                                    ),
                                }
                            ],
                        },
                    ]
                )
    if no_diff_hosts:
        body["blocks"].append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":white_check_mark:\t_{', '.join(no_diff_hosts)}_",
                    },
                    {"type": "mrkdwn", "text": "No operational diffs"},
                ],
            },
        )
    if check_number == total_checks:
        body["blocks"].append({"type": "divider"})

    requests.post(url=slack_webhook, json=body)
