from dictdiffer import diff  # type: ignore
from collections import defaultdict
import concurrent.futures
from typing import List, Any, Tuple, Optional, Dict, Union
from ananke.post_checks.gnmi.telemetry import subscribe
from ananke.connectors.shared import Target


class CheckSubscriber:
    """
    Object responsible for subscribing to a device, storing the initial state, and
    providing functionality to diff against the initial state. Includes a number of
    formatting methods to improve compatibility between platforms, etc.
    """

    def __init__(self, target_dict: Any, paths: List[str]) -> None:
        self.target_dict = target_dict
        if not paths:
            raise ValueError("No check paths provided")
        self.paths = paths
        self.get_initial_state()

    @staticmethod
    def format_bgp_peer(response: Any) -> Any:
        """
        Format BGP neighbors to remove dynamic fields, etc
        """
        if "neighbor-address" in response["val"]:
            if "state" in response["val"]:
                response["val"] = response["val"]["state"]
            response["val"] = {
                "neighbor-address": response["val"]["neighbor-address"],
                "session-state": (
                    "UP"
                    if "session-state" in response["val"]
                    and response["val"]["session-state"] == "ESTABLISHED"
                    else "DOWN"
                ),
            }
            if "enabled" in response["val"]:
                response["enabled"] = response["val"]["enabled"]
            if "description" in response["val"]:
                response["description"] = (response["val"]["description"],)
            if "peer-as" in response["val"]:
                response["peer-as"] = (response["val"]["peer-as"],)
        return response

    @staticmethod
    def format_interface(response: Any) -> Any:
        """
        Format interfaces to remove dynamic fields, etc
        """

        def _sanitize_counters(value: Any) -> Any:
            def _create_new_counters(counters: Any) -> Any:
                new_counters = {}
                for key in counters.keys():
                    if "err" in key or "discard" in key:
                        new_counters[key] = counters[key]
                return new_counters

            if "counters" in value:
                return _create_new_counters(value["counters"])
            elif "state" in value:
                if "counters" in value["state"]:
                    return _create_new_counters(value["state"]["counters"])
            return None

        if response["path"].endswith("/state/counters"):
            new_counters = _sanitize_counters(response["val"])
            del response["val"]["counters"]
            response["val"]["counters"] = new_counters
        elif response["path"].endswith("/state"):
            new_counters = _sanitize_counters(response["val"])
            if "counters" in response["val"]:
                del response["val"]["counters"]
            elif "name" in response["val"]:
                if "state" in response["val"]:
                    response["val"] = response["val"]["state"]
                oper_status = "DOWN"
                if "oper-status" in response["val"]:
                    oper_status = response["val"]["oper-status"]
                response["val"] = {
                    "name": response["val"]["name"],
                    "admin-status": response["val"]["admin-status"],
                    "oper-status": oper_status,
                }
                if new_counters:
                    response["val"]["counters"] = new_counters
        # for some reason ethernet/state/counters ends with a bare interface path
        elif response["path"].endswith("]"):
            if "counters" in response["val"]["ethernet"]["state"]:
                new_counters = _sanitize_counters(response["val"]["ethernet"]["state"])
                del response["val"]["ethernet"]["state"]["counters"]
                response["val"]["ethernet"]["state"]["counters"] = new_counters
        return response

    def split_unified_responses(self, poll: Any):
        """
        This method is required because NXOS and IOS-XR return responses differently.
        We take the IOS-XR approach here where every response is split (i.e. interfaces
        have their own response, rather than all being held in a list under one response
        ). We want to treat them the same way elsewhere, so we split out the unified
        responses of NXOS here to mimic IOS-XR.
        """
        responses = []
        for response in poll:
            if response["path"] == "network-instances":
                for instance in response["val"]["network-instance"]:
                    inst = (
                        f"network-instances/network-instance[name={instance['name']}]/"
                    )
                    for protocol in instance["protocols"]["protocol"]:
                        prot = (
                            inst
                            + f"protocols/protocol[identifier={protocol['identifier']}]"
                            + f"[name={protocol['name']}]/"
                        )
                        for neighbor in protocol["bgp"]["neighbors"]["neighbor"]:
                            if "afi-safis" in neighbor:
                                for afi_safi in neighbor["afi-safis"]["afi-safi"]:
                                    path = (
                                        prot
                                        + "bgp/neighbors/neighbor[neighbor-address="
                                        + f"{neighbor['neighbor-address']}]/afi-safis/"
                                        + "afi-safi[afi-safi-name="
                                        + f"{afi_safi['afi-safi-name']}]/"
                                        + "/state"
                                    )
                                    responses.append(
                                        {
                                            "path": path,
                                            "val": afi_safi,
                                        }
                                    )
                            else:
                                path = (
                                    prot
                                    + "bgp/neighbors/neighbor[neighbor-address="
                                    + f"{neighbor['neighbor-address']}]/state"
                                )
                                path = path
                                responses.append(
                                    {
                                        "path": path,
                                        "val": neighbor,
                                    }
                                )
            elif response["path"] == "interfaces":
                for interface in response["val"]["interface"]:
                    if "ethernet" in interface:
                        path = f"interfaces/interface[name={interface['name']}]"
                        responses.append(
                            {
                                "path": path,
                                "val": interface,
                            }
                        )
                    else:
                        path = f"interfaces/interface[name={interface['name']}]/state"
                        responses.append(
                            {
                                "path": path,
                                "val": interface,
                            }
                        )
            elif response["path"] == "lldp":
                for interface in response["val"]["interfaces"]["interface"]:
                    for neighbor in interface["neighbors"]["neighbor"]:
                        intf = f"lldp/interfaces/interface[name={interface['name']}]/"
                        path = intf + f"/neighbors/neighbor[id={neighbor['id']}]/state"
                        responses.append(
                            {
                                "path": path,
                                "val": neighbor,
                            }
                        )
        if not responses:
            return poll
        return responses

    def populate_state(self, poll: Any, state_container: Any) -> Any:
        """
        Common population method. Used for both initial state and subsequent polls.
        """
        responses = self.split_unified_responses(poll)
        for response in responses:
            if response["path"].startswith("network-instances"):
                formatted = self.format_bgp_peer(response)["val"]
            elif response["path"].startswith("interfaces"):
                formatted = self.format_interface(response)["val"]
            else:
                formatted = response["val"]
            state_container[response["path"]].update(formatted)
        return state_container

    def poll(self) -> Any:
        """
        Poll the device and return the response
        """
        return next(
            subscribe(
                target_dict=self.target_dict,
                paths=self.paths,
            )
        )

    def get_initial_state(self) -> None:
        """
        Populate the initial state of the device
        """
        self.initial_state: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.initial_state = self.populate_state(
            self.poll()["update"]["update"], self.initial_state
        )

    def diff_from_initial(self, tolerance: Optional[int] = None) -> List[Any]:
        """
        Diff the current state against the initial state
        """
        poll_state = self.populate_state(
            self.poll()["update"]["update"], defaultdict(dict)
        )
        diffs: List[Tuple[str, Union[str, List[str]]]] = []
        removed_paths = set(list(self.initial_state.keys())) - set(
            list(poll_state.keys())
        )
        diffs.extend([(path, "REMOVED") for path in removed_paths])
        for path in poll_state.keys():
            if path in self.initial_state:
                if response_diffs := list(
                    diff(
                        self.initial_state[path],
                        poll_state[path],
                        tolerance=tolerance / 100 if tolerance else None,
                    )
                ):
                    diffs.append((path, response_diffs))
            else:
                diffs.append((f"{path} -- {poll_state[path]}", "ADDED"))
        return diffs


def init_check_object(target_dicts: Any, paths: List[str]) -> CheckSubscriber:
    """
    Wrapper to initialize the check object, for use with concurrent.futures
    """
    return CheckSubscriber(target_dicts, paths)


def poll_device(
    check_object: CheckSubscriber, tolerance: Optional[int] = 10
) -> Tuple[str, List[Any]]:
    """
    Wrapper to run poll on given check object, for use with concurrent.futures
    """
    return check_object.target_dict["target"][0], check_object.diff_from_initial(
        tolerance=tolerance
    )


class StatusCheck:
    def __init__(
        self,
        targets: List[Target],
        paths: List[str],
    ):
        self.targets = targets
        self.paths = paths
        self.check_objects: List[CheckSubscriber] = []
        self.init_check_objects()

    def init_check_objects(self) -> None:
        """
        Initializes the check objects for each host concurrently
        """
        target_dicts = [target.connector.target_dict for target in self.targets]
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for check_object in executor.map(
                init_check_object,
                target_dicts,
                [self.paths] * len(self.targets),
            ):
                self.check_objects.append(check_object)

    def poll(self, tolerance: Optional[int]) -> Any:
        """
        Polls each check object and diffs against initial state
        """
        self.results = {}
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for hostname, diffs in executor.map(
                poll_device, self.check_objects, [tolerance] * len(self.check_objects)
            ):
                self.results[hostname] = diffs
