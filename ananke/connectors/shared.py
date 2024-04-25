import os
import logging
from pathlib import Path
from typing import Any, List, Optional, Literal
from dataclasses import dataclass, field
from ananke.struct.config import Config, ConfigPack
from pygnmi.client import gNMIException

logger = logging.getLogger(__name__)


WRITE_METHODS = Optional[Literal["update", "replace"]]


@dataclass
class AnankeResponseMessage:
    text: str
    priority: Literal[1, 2, 3] = 3


@dataclass
class AnankeResponse:
    source: str
    messages: List[AnankeResponseMessage] = field(default_factory=list)
    body: List[Any] = field(default_factory=list)
    output: List[Any] = field(default_factory=list)


def get_password(username: str, variables: Any) -> str:
    """
    Attempts to get a password for a given username either from variables or defined
    environment variables.
    """
    if password := variables.get(f"ANANKE_CONNECTOR_PASSWORD_{username}"):
        return password
    elif password := variables.get("ANANKE_CONNECTOR_PASSWORD"):
        return password

    if password := os.environ.get(f"ANANKE_CONNECTOR_PASSWORD_{username}"):
        return password
    elif password := os.environ.get("ANANKE_CONNECTOR_PASSWORD"):
        return password
    raise ValueError(f"Could not derive password for username {username}")


class Connector:
    def __init__(self, target_id: str, config: Config):
        self.target_id = target_id
        self.config = config
        self.settings = config.settings
        self.variables = config.variables
        self.config_transform: bool = self.should_transform_config()

    def should_transform_config(self) -> bool:
        """
        Inform that queried device/service has a transform module defined
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
        if "platform" in self.variables:
            self.platform_id = self.variables["platform"]["os"]
        elif "service-id" in self.variables:
            self.platform_id = self.variables["service-id"]
        else:
            return False
        if self.platform_id.replace("-", "_") in transform_modules:
            logger.debug(
                "Transform module matching platform found, marking for transform"
            )
            return True
        return False

    def _transform_config(self, pack: ConfigPack) -> ConfigPack:
        """
        Runs pack through config transform
        """
        module_name = self.platform_id.replace("-", "_")
        logger.debug(
            "Running transform function from {path}/{mod}".format(
                path=self.settings["transforms"]["module-directory"], mod=module_name
            )
        )
        import importlib

        transform_module = importlib.import_module(module_name, package=None)
        transform_function = getattr(transform_module, "transform")
        return transform_function(pack)

    @staticmethod
    def deploy(
        target: Any,  # classifying as any to avoid circular imports with dispatch
        write_method: WRITE_METHODS,
        dry_run: bool,
    ) -> None:
        """
        Shared deploy function used by all connectors. Designed to run in parallel from
        dispatch executor. Static method so that the ThreadPoolExecutor can run it in a
        map as an uninstantiated method with an instance passed in.
        """
        logger.debug(
            "Starting deploy process for {}".format(target.connector.target_id)
        )
        response = AnankeResponse(target.connector.target_id)
        for pack in target.config.packs:
            if dry_run:
                pack.tags.append("dry-run")
            if write_method:
                pack.write_method = write_method
            pack = (
                target.connector._transform_config(pack)
                if target.connector.config_transform
                else pack
            )
            response.body.append(
                {
                    "path": pack.path,
                    "write-method": pack.write_method,
                    "content": pack.content,
                }
            )
            if not dry_run:
                if (
                    "management" in target.config.variables
                    and "disable-set" in target.config.variables["management"]
                    and target.config.variables["management"]["disable-set"]
                ):
                    logger.debug(
                        "disable-set enabled for {}, skipping".format(
                            target.connector.target_id
                        )
                    )
                    response.messages.append(
                        AnankeResponseMessage(
                            text="Write disabled, skipping", priority=2
                        )
                    )
                else:
                    try:
                        logger.debug("Deploying config pack {}".format(pack.path))
                        response.output.append(
                            target.connector._set_config(config_pack=pack)
                        )
                        response.messages.append(
                            AnankeResponseMessage(
                                text=f"Config for {pack.path} pushed to device"
                            )
                        )
                    except gNMIException as err:
                        response.messages.append(
                            AnankeResponseMessage(
                                text=f"Config for {pack.path} failed: Error: {err}",
                                priority=1,
                            )
                        )
            else:
                response.messages.append(AnankeResponseMessage(text="Config dry-run"))
        return response
