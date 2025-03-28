import os
import logging
import concurrent.futures
from pathlib import Path
from ruamel.yaml import YAML  # type: ignore
from typing import Any, Tuple, Dict, List, Optional, Set
from ananke.struct.config import Config
from ananke.connectors.gnmi import GnmiDevice
from ananke.connectors.shared import Connector, AnankeResponse, get_connector, Target
from ananke.post_checks.telemetry import StatusCheck

CONFIG_PACK = Tuple[str, Any]
CONFIG_DIR = os.environ.get("ANANKE_CONFIG")

logger = logging.getLogger(__name__)


class Dispatch:
    """
    Object for preparing execution. Reads global and target settings and populates
    list of target objects from list of target hostnames/roles/services
    """

    def __init__(
        self,
        targets: Dict[Optional[str], Set[str]],
        deploy_tags: List[str] = [],
        post_checks: bool = False,
    ):
        self.settings = self.get_settings()
        self.secrets = None
        self.variables: Dict[str, Any] = self.get_variables()
        if self.settings["vault"]:
            self.secrets = self.build_vault()
        parsed_targets = self.parse_targets(targets, self.settings.get("domain-name"))
        self.targets: List[Target] = self.build_targets(
            targets=parsed_targets, deploy_tags=deploy_tags
        )
        if post_checks and "dry-run" not in deploy_tags:
            check_hosts: List[Target] = []
            for target in self.targets:
                short_name = target.connector.target_id.split(".")[0]
                management = self.variables[short_name]["management"]
                if "disable-set" in management and management["disable-set"]:
                    continue
                check_hosts.append(target)
            if "paths" not in self.settings["post-checks"]:
                raise ValueError("No paths specified for post-checks")
            self.post_status = StatusCheck(
                check_hosts,
                self.settings["post-checks"]["paths"],
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
        self, targets: Dict[Optional[str], Set[str]], deploy_tags: List[str] = []
    ) -> List[Target]:
        """
        Builds a list of Target objects consisting of relevant details for connecting
        to the target
        """
        target_list = []
        for target, sections in targets.items():
            target_vars = self.variables[target.split(".")[0]]

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
            connector = get_connector(
                target_id=target, config=config, connector_cls=GnmiDevice
            )
            target = Target(connector=connector, config=config)
            target_list.append(target)
        return target_list

    def get_variable_files(self) -> List[Path]:
        """
        Get all variable files
        """
        variable_paths = [
            path
            for path in Path(f"{CONFIG_DIR}/").rglob("vars.yaml")
            if "devices" in path.parts
        ]
        if not variable_paths:
            logger.warning(
                "Coule not find variable files in {dir}".format(dir=CONFIG_DIR)
            )
        return variable_paths

    def get_variables(self) -> Dict[str, str]:
        """
        Get local device variables from vars.yaml
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
            for target, _ in given_targets.items():
                if target not in found_roles and target not in found_targets:
                    logger.warning(
                        "'{target}' does not appear to be a device or role. Make sure "
                        "a vars.yaml file exists if it is a device.".format(
                            target=target
                        )
                    )

        if list(targets.keys()) == [None]:
            targets = {
                path.parts[-2]: targets[None] for path in self.get_variable_files()
            }

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

        _verify_targets(given_targets=targets, found_targets=devices, found_roles=roles)

        target_devices = {
            f"{target}.{domain_name}": sections if domain_name else target
            for target, sections in targets.items()
            if target in devices
        }
        target_roles = {
            target: sections for target, sections in targets.items() if target in roles
        }
        target_devices_from_roles = {}
        for device, device_vars in self.variables.items():
            if "roles" in device_vars:
                target_devices_from_roles.update(
                    {
                        (f"{device}.{domain_name}" if domain_name else device): sections
                        for role, sections in target_roles.items()
                        if role in device_vars["roles"]
                    }
                )

        return {**target_devices_from_roles, **target_devices}
