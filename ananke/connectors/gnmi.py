import json
import os
from pathlib import Path
import logging
from typing import Any, Literal, List, Tuple, Union, Optional
from pygnmi import client  # typing: ignore
from ananke.struct.config import ConfigPack


WRITE_METHODS = Optional[Literal["update", "replace"]]
logger = logging.getLogger(__name__)


class GnmiDevice:
    """
    Class for interacting with gNMI server. This involves establishing a gNMI session
    and running calls towards the device.
    """

    def __init__(
        self,
        hostname: str,
        settings: Any,
        variables: Any,
        username: str,
        password: str,
    ):
        self.hostname = hostname
        self.settings = settings
        self.variables = variables
        self.config_transform: bool = self._should_transform_config()
        port = 50051
        if gnmi_port := self.variables["management"].get("gnmi-port"):
            port = gnmi_port
        target_dict = {
            "target": (hostname, port),
            "username": username,
            "password": password,
        }
        if tls_server := self.variables["management"].get("tls-server"):
            target_dict["override"] = tls_server
        if cert := self._get_cert():
            target_dict["path_cert"] = cert
        else:
            target_dict["insecure"] = True
        self.session = client.gNMIclient(**target_dict)
        logger.info(
            "Creating GnmiDevice instance for {username}@{hostname}:{port} "
            "with cert {cert}. TLS server name override: {tls_server}".format(
                username=username,
                hostname=hostname,
                port=port,
                cert=cert,
                tls_server=tls_server,
            )
        )

    def _should_transform_config(self) -> bool:
        """
        Inform that this platform has a transform module defined
        """
        if "transforms" not in self.settings or not self.settings["transforms"].get(
            "module-directory"
        ):
            return False
        transform_modules = [
            str(file.stem)
            for file in Path(self.settings["transforms"]["module-directory"]).glob(
                "*.py"
            )
            if str(file.stem) != "__init__"
        ]
        logger.debug(
            "Transform modules discovered: {transform_modules}".format(
                transform_modules=transform_modules
            )
        )
        if self.variables["platform"]["os"].replace("-", "_") in transform_modules:
            logger.debug(
                "Transform module matching platform found, marking for transform"
            )
            return True
        return False

    def _get_cert(self) -> Optional[str]:
        """
        Chooses certificate based on variables and settings
        """
        if not any(
            [
                self.settings.get("certificate"),
                self.settings["certificate"],
                os.environ.get("ANANKE_CERTIFICATE_DIR"),
            ]
        ):
            return
        if cert_path := os.environ.get("ANANKE_CERTIFICATE_DIR"):
            path = cert_path
        else:
            path = self.settings["certificate"]["directory"]
        cert = self.settings["certificate"]["name"]
        if vars_cert := self.variables["management"].get("certificate"):
            cert = vars_cert
        certs = [str(file.parts[-1]) for file in Path(path).glob("*")]
        if cert not in certs:
            raise ValueError(f"Configured cert {cert} not found in {path}")
        return f"{path}/{cert}"

    def _set_config(
        self,
        config_pack: ConfigPack,
    ) -> Any:
        """
        Set config method
        Args:
            config_pack: ConfigPack dataclass of gNMI path, contents, and write method
        """
        logger.debug(
            "Pushing config with set: {config_pack}".format(config_pack=config_pack)
        )
        with self.session as session:
            kwargs = {
                config_pack.write_method: [(config_pack.path, config_pack.content)]
            }
            try:
                return session.set(**kwargs)
            except client.gNMIException as gnmi_error:
                if (
                    "'YANG framework' detected the 'fatal' condition 'Operation failed'"
                    in str(gnmi_error)
                ):
                    logger.warning("Caught gNMI exception, trying again...")
                    return session.set(**kwargs)
                else:
                    raise client.gNMIException(gnmi_error)

    def _get_config(self, path: str, operational: bool) -> Any:
        """
        Get config method
        Args:
            path: gNMI path to get config from
        """
        with self.session as session:
            if operational:
                return session.get(path=[path])
            return session.get(path=[path], datatype="config")

    def _get_capabilities(self) -> Any:
        """
        Get capabilities method
        """
        with self.session as session:
            return session.capabilities()

    def _transform_config(self, pack: ConfigPack) -> ConfigPack:
        """
        Runs pack through config transform
        """
        module_name = self.variables["platform"]["os"].replace("-", "_")
        logger.debug(
            "Running transform function from {path}/{mod}".format(
                path=self.settings["transforms"]["module-directory"], mod=module_name
            )
        )
        import importlib

        transform_module = importlib.import_module(module_name, package=None)
        transform_function = getattr(transform_module, "transform")
        return transform_function(pack)

    def push_config(
        self, write_method: WRITE_METHODS, config: List[ConfigPack], dry_run: bool
    ) -> Tuple[Union[Any, None], Union[Any, None]]:
        """
        Config push method for all or parts of the device config.
        Args:
            write_method: Optional write method to use (either update or replace)
            config: List of ConfigPack objects
            dry_run: Boolean flag for skipping config push
        """
        body = []
        output = []
        if (
            "disable-set" in self.variables["management"]
            and self.variables["management"]["disable-set"]
        ):
            logger.debug(
                "disable-set enabled for {self.hostname}, skipping".format(
                    hostname=self.hostname
                )
            )
            return None, None
        for pack in config:
            if write_method:
                pack.write_method = write_method
            pack = self._transform_config(pack) if self.config_transform else pack
            body.append(
                {
                    "path": pack.path,
                    "write-method": pack.write_method,
                    "content": pack.content,
                }
            )
            if not dry_run:
                output.append(self._set_config(config_pack=pack))
        return json.dumps(body, indent=2), (
            json.dumps(output, indent=2) if output else None
        )

    def get_config(
        self, path: str, oneline: bool, operational: bool, include_meta: bool = False
    ) -> Any:
        """
        Get config from device with gNMI path. By default returns dict with indents.
        """
        content = self._get_config(path=path, operational=operational)
        if not include_meta:
            content = content["notification"][0]["update"][0]["val"]
        if not oneline:
            return json.dumps(content, indent=2)
        return content

    def get_capabilities(self) -> Any:
        """
        Get capabilities from device
        """
        return self._get_capabilities()
