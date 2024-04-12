import json
import logging
from pathlib import Path
from typing import Any, List, Tuple, Union, Optional, Literal
from ananke.struct.config import ConfigPack

logger = logging.getLogger(__name__)


WRITE_METHODS = Optional[Literal["update", "replace"]]


class Connector:
    def __init__(self, settings: Any, variables: Any):
        self.settings = settings
        self.variables = variables
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

    def deploy(
        self, write_method: WRITE_METHODS, config: List[ConfigPack], dry_run: bool
    ) -> Tuple[Union[Any, None], Union[Any, None]]:
        """
        Shared deploy function used by all connectors. Runs through some logic and returns
        data in a predefined format for reuse with all connectors.
        """
        body = []
        output = []
        for pack in config:
            if write_method:
                pack.write_method = write_method
            pack = self._transform_config(pack) if self.config_transform else pack
            body.append(
                {
                    "target": pack.target_id,
                    "path": pack.path,
                    "write-method": pack.write_method,
                    "content": pack.content,
                }
            )
            if not dry_run:
                if (
                    "management" in self.variables
                    and "disable-set" in self.variables["management"]
                    and self.variables["management"]["disable-set"]
                ):
                    logger.debug(
                        "disable-set enabled for {}, skipping".format(self.target_id)
                    )
                    return None, None
                output.append(self._set_config(config_pack=pack))
        return json.dumps(body, indent=2), (
            json.dumps(output, indent=2) if output else None
        )
