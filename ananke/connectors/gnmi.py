import json
import os
from pathlib import Path
import logging
from typing import Any, Literal, List, Tuple, Union, Optional
from pygnmi import client  # typing: ignore
from ananke.struct.config import Config, ConfigPack
from ananke.connectors.shared import Connector, get_password


logger = logging.getLogger(__name__)


class GnmiDevice(Connector):
    """
    Class for interacting with gNMI server. This involves establishing a gNMI session
    and running calls towards the device.
    """

    def __init__(self, target_id: str, config: Config):
        super().__init__(config=config, target_id=target_id)
        self.config = config
        port = 50051
        if gnmi_port := self.variables["management"].get("gnmi-port"):
            port = gnmi_port
        username = self.settings["username"]
        if "username" in config.variables:
            username = config.variables["username"]
        password = get_password(username, config.variables)
        target_dict = {
            "target": (target_id, port),
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
            "Creating GnmiDevice instance for {username}@{target_id}:{port} "
            "with cert {cert}. TLS server name override: {tls_server}".format(
                username=username,
                target_id=target_id,
                port=port,
                cert=cert,
                tls_server=tls_server,
            )
        )

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

    # def deploy(
    #     self, write_method: WRITE_METHODS, config: List[ConfigPack], dry_run: bool
    # ) -> Tuple[Union[Any, None], Union[Any, None]]:
    #     """
    #     Service-specific wrapper for generic shared-deploy function. Mostly here just
    #     to pass in the custom _set_config() function and present a uniform function
    #     to dispatch.
    #     """
    #     return shared_deploy(
    #         target=self.target_id,
    #         variables=self.variables,
    #         config=config,
    #         write_method=write_method,
    #         dry_run=dry_run,
    #         set_func=self._set_config,
    #         transform_func=self._transform_config if self.config_transform else None,
    #     )

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
