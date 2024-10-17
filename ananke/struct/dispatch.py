import os
import logging
import concurrent.futures
from pathlib import Path
from ruamel.yaml import YAML  # type: ignore
from dataclasses import dataclass
from typing import Any, Tuple, Dict, List, Optional, Set, Union, Literal
from ananke.struct.config import Config
from ananke.connectors.gnmi import GnmiDevice
from ananke.connectors.services import PacketFabric, Megaport
from ananke.connectors.shared import Connector, AnankeResponse

CONFIG_PACK = Tuple[str, Any]
CONFIG_DIR = os.environ.get("ANANKE_CONFIG")

logger = logging.getLogger(__name__)


@dataclass
class Target:
    connector: Union[GnmiDevice, PacketFabric, Megaport]
    config: Config


class Dispatch:
    """
    Object for preparing execution. Reads global and target settings and populates
    list of target objects from list of target hostnames/roles/services
    """

    def __init__(
        self,
        targets: Dict[Optional[str], Set[str]],
        target_type: Literal["device", "service"],
        deploy_tags: List[str],
    ):
        if target_type not in ["device", "service"]:
            raise ValueError("Target type must be one of 'device' or 'service'")
        self.target_type = target_type
        self.settings = self.get_settings()
        self.secrets = None
        self.variables: Dict[str, Any] = self.get_variables()
        if self.settings["vault"]:
            self.secrets = self.build_vault()
        parsed_targets = self.parse_targets(targets, self.settings.get("domain-name"))
        self.targets: List[Target] = self.build_targets(
            targets=parsed_targets, deploy_tags=deploy_tags
        )

    def concurrent_deploy(self, method: str) -> List[AnankeResponse]:
        """
        Deploy config for all targets concurrently
        """
        self.deploy_results: List[AnankeResponse] = []
        iter_len = range(len(self.targets))
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for result in executor.map(
                Connector.deploy,
                self.targets,
                [method for _ in iter_len],
            ):
                self.deploy_results.append(result)

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

    def build_targets(
        self, targets: Dict[Optional[str], Set[str]], deploy_tags: List[str]
    ) -> List[Target]:
        """
        Builds a list of Target objects consisting of relevant details for connecting
        to the target
        """
        target_list = []
        for target, sections in targets.items():
            if target.split(".")[0] in self.variables:
                target_vars = self.variables[target.split(".")[0]]
            else:
                target_vars = self.variables["services"][target]

            if self.secrets:
                target_vars.update(self.secrets)
            config = Config(
                target_id=target,
                sections=sections,
                settings=self.settings,
                variables=target_vars,
            )
            # this is kind of a dumb hack, but currently the only use we have for deploy
            # tags is universal to all packs belonging to a Config object, so we just
            # set them here
            for pack in config.packs:
                pack.tags = deploy_tags
            if self.target_type == "device":
                connector = GnmiDevice(
                    target_id=target,
                    config=config,
                )
            else:
                if target_vars["service-id"] == "megaport":
                    connector = Megaport(target_id=target, config=config)
                elif target_vars["service-id"] == "packetfabric":
                    connector = PacketFabric(target_id=target, config=config)
            target = Target(connector=connector, config=config)
            target_list.append(target)
        return target_list

    def get_variable_files(self) -> List[Path]:
        """
        Get all variable files
        """
        return [
            path
            for path in Path(f"{CONFIG_DIR}/{self.target_type}s").rglob("vars.yaml")
        ]

    def get_variables(self) -> Dict[str, str]:
        """
        Get local device/service variables from vars.yaml
        """
        vars = {}
        for file in self.get_variable_files():
            vars[file.parts[-2]] = YAML().load(open(str(file)))
        return vars

    def get_settings(self) -> Optional[Dict[str, str]]:
        """
        Populate self.settings with contents from global settings file
        """
        if not CONFIG_DIR:
            raise ValueError("ANANKE_CONFIG environment variable must be set")
        if os.path.exists(f"{CONFIG_DIR}/settings.yaml"):
            yaml = YAML()
            return yaml.load(open(f"{CONFIG_DIR}/settings.yaml"))

    def parse_targets(
        self, targets: Dict[Optional[str], Set[str]], domain_name: Optional[str]
    ) -> Set[str]:
        """
        Given a list of roles and/or hostnames return a set of hostnames
        """

        def _verify_targets(
            given_targets: List[str],
            found_targets: List[str],
            found_roles: List[str] = [],
        ):
            """
            Generic service/role/device verification function
            """
            message_suffix = (
                self.target_type + " or role"
                if self.target_type == "device"
                else self.target_type
            )
            for target, _ in given_targets.items():
                if target not in found_roles and target not in found_targets:
                    logger.warning(
                        "Target '{target}' does not appear to be a "
                        "{message_suffix}".format(
                            target=target, message_suffix=message_suffix
                        )
                    )

        if list(targets.keys()) == [None]:
            targets = {
                path.parts[-2]: targets[None] for path in self.get_variable_files()
            }

        if self.target_type == "device":
            roles = set()
            for _, device_vars in self.variables.items():
                roles.update(device_vars.get("roles", []))
            devices = list(self.variables.keys())

            if "all" in targets:
                return {
                    device: sections
                    for device in devices
                    for _, sections in targets.items()
                }

            _verify_targets(
                given_targets=targets, found_targets=devices, found_roles=roles
            )

            target_devices = {
                f"{target}.{domain_name}": sections if domain_name else target
                for target, sections in targets.items()
                if target in devices
            }
            target_roles = {
                target: sections
                for target, sections in targets.items()
                if target in roles
            }
            target_devices_from_roles = {}
            for device, device_vars in self.variables.items():
                if "roles" in device_vars:
                    target_devices_from_roles.update(
                        {
                            (
                                f"{device}.{domain_name}" if domain_name else device
                            ): sections
                            for role, sections in target_roles.items()
                            if role in device_vars["roles"]
                        }
                    )

            return {**target_devices_from_roles, **target_devices}
        services = list(self.variables.keys())
        _verify_targets(given_targets=targets, found_targets=services)
        return {
            target: sections
            for target, sections in targets.items()
            if target in services
        }
