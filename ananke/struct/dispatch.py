from pathlib import Path
from ruamel.yaml import YAML  # type: ignore
import os
import logging
from dataclasses import dataclass
from typing import Any, Tuple, Dict, List, Optional, Set

CONFIG_PACK = Tuple[str, Any]
CONFIG_DIR = os.environ.get("ANANKE_CONFIG")

logger = logging.getLogger(__name__)


@dataclass
class Device:
    hostname: str
    username: str
    password: str
    variables: Dict[str, str]


class Dispatch:
    """
    Object for preparing execution. Reads global and device settings and populates
    list of target Device objects from list of target hostnames/roles
    """

    def __init__(self, targets: Tuple[str]):
        self.settings = self.get_settings()
        self.secrets = None
        self.device_variables: Dict[str, Any] = self.get_device_variables()
        if self.settings["vault"]:
            self.secrets = self.build_vault()
        self.target_devices: List[Device] = self.build_targets(
            self.parse_targets(targets, self.settings.get("domain-name"))
        )

    def build_vault(self) -> Dict[str, str]:
        """
        Instantiate and return vault secrets
        """
        from ananke.struct.vault import Vault  # type: ignore

        role_id = self.settings["vault"]["role-id"]
        paths = self.settings["vault"]["paths"]
        mount_point = self.settings["vault"]["mount-point"]
        vault_secret = os.environ.get("ANANKE_VAULT_SECRET")
        if not vault_secret:
            raise ValueError(
                "ANANKE_VAULT_SECRET env variable must be populated for vault use"
            )
        return Vault(
            vault_role_id=role_id,
            paths=paths,
            url=self.settings["vault"]["url"],
            mount_point=mount_point,
            vault_secret=vault_secret,
        ).keys

    def get_password(self, username: str) -> str:
        """
        Attempts to get a password for a given username either from vault or defined
        environment variables.
        """
        if self.secrets:
            if password := self.secrets.get(f"ANANKE_CONNECTOR_PASSWORD_{username}"):
                return password
            elif password := self.secrets.get("ANANKE_CONNECTOR_PASSWORD"):
                return password

        if password := os.environ.get(f"ANANKE_CONNECTOR_PASSWORD_{username}"):
            return password
        elif password := os.environ.get("ANANKE_CONNECTOR_PASSWORD"):
            return password
        raise ValueError(f"Could not derive password for username {username}")

    def build_targets(self, targets: Set[str]) -> List[Device]:
        """
        Builds a list of Device objects consisting of hostname, username, password, and
        local device variables
        """
        device_list = []
        for device in targets:
            device_vars = self.device_variables[device.split(".")[0]]
            username = self.settings["username"]
            if "username" in device_vars:
                username = device_vars["username"]
            password = self.get_password(username)

            if self.secrets:
                device_vars.update(self.secrets)
            device_list.append(
                Device(
                    hostname=device,
                    username=username,
                    password=password,
                    variables=device_vars,
                )
            )
        return device_list

    def get_device_variables(self) -> Dict[str, str]:
        """
        Get local device variables from vars.yaml
        """
        device_vars = {}
        for file in Path(f"{CONFIG_DIR}/devices").rglob("vars.yaml"):
            device_vars[file.parts[-2]] = YAML().load(open(str(file)))
        return device_vars

    def get_settings(self) -> Optional[Dict[str, str]]:
        """
        Populate self.settings with contents from global settings file
        """
        if not CONFIG_DIR:
            raise ValueError("ANANKE_CONFIG environment variable must be set")
        if os.path.exists(f"{CONFIG_DIR}/settings.yaml"):
            yaml = YAML()
            return yaml.load(open(f"{CONFIG_DIR}/settings.yaml"))

    def parse_targets(self, targets: List[str], domain_name: Optional[str]) -> Set[str]:
        """
        Given a list of roles and/or hostnames return a set of hostnames
        """
        roles = set()
        for _, device_var in self.device_variables.items():
            roles.update(device_var["roles"])
        devices = list(self.device_variables.keys())

        if "all" in targets:
            return set(devices)

        for target in targets:
            if target not in roles and target not in devices:
                raise RuntimeError(
                    f"Target '{target}' does not appear to be a device or role"
                )

        target_devices = [
            f"{target}.{domain_name}" if domain_name else target
            for target in targets
            if target in devices
        ]
        target_roles = [target for target in targets if target in roles]
        target_devices_from_roles = []
        for device, device_vars in self.device_variables.items():
            if "roles" in device_vars:
                target_devices_from_roles.extend(
                    [
                        f"{device}.{domain_name}" if domain_name else device
                        for role in target_roles
                        if role in device_vars["roles"]
                    ]
                )

        return set(target_devices_from_roles + target_devices)
