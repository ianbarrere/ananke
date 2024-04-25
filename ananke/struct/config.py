import jinja2  # type: ignore
import re
import json
import os
import logging
from pathlib import Path, PosixPath
from ruamel.yaml import YAML  # type: ignore
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Any, Tuple, Dict, List, Set, Literal

CONFIG_PACK = Tuple[str, Any]
CONFIG_DIR = os.environ.get("ANANKE_CONFIG")

logger = logging.getLogger(__name__)


@dataclass
class ConfigPack:
    """
    path: gNMI/REST/other path that defines where the content is going
    original_content: Original content before transform, sometimes needed late in the
        game for comparison on fields we don't send
    content: Modified content after transform
    write_method: Either replace or update
    """

    path: str
    original_content: Any
    content: Any
    write_method: Literal["replace", "update"] = "replace"
    tags: List[str] = field(default_factory=list)


class Config:
    """
    Object for handling configuration of a device. Includes parsing and variable
    substitution. Holds configuration in packs attribute, used by connectors.
    """

    def __init__(
        self,
        target_id: str,
        settings: Dict[Any, Any],
        variables: Dict[str, str],
        sections: Tuple[str] = (),
    ):
        if not CONFIG_DIR:
            raise ValueError("ANANKE_CONFIG environment variable must be set")
        self.target_id = target_id.split(".")[0]
        self.settings = settings
        self.variables = variables
        self.file_paths = defaultdict(list)
        self.mapping = defaultdict(list)
        self.roles: List[str] = self._get_device_roles()
        self.parse_config()
        self.sections = self._resolve_sections(sections)
        self.merge_paths()
        self.packs: List[ConfigPack] = self.build_packs()
        logger.info(
            "Config object initialized for {target_id} and section {section}".format(
                target_id=self.target_id, section=self.sections
            )
        )
        logger.debug("Global settings: {settings}".format(settings=self.settings))
        logger.debug("Device variables: {vars}".format(vars=self.variables))
        logger.debug("Device roles: {roles}".format(roles=self.roles))
        logger.debug("Config content: {packs}".format(packs=self.packs))

    def _resolve_sections(self, sections: Set[str]) -> Set[str]:
        """
        Given a set of possible paths and/or filenames return a set of only paths
        """
        if not isinstance(sections, set):
            raise ValueError("Sections must be a set of values")
        resolved_sections = set()
        for section in sections:
            if re.search("\.yaml\.j2$", section):
                resolved_sections.update(self.file_paths[section])
            else:
                resolved_sections.add(section)
        return resolved_sections

    def _get_device_roles(self) -> List[str]:
        """
        Currently only supports roles as defined in vars.yaml.
        Would be nice to expand in the future to fetch from netbox for example.
        """
        if roles := self.variables.get("roles"):
            return roles
        return []

    def _get_files(self) -> List[PosixPath]:
        """
        Helper method to compute list of files for config. Hostname directory, followed
        by all applicable roles, followed by all, in that order.
        """
        files = [file for file in Path(CONFIG_DIR).rglob("*.yaml.j2")]
        host_files = [str(file) for file in files if file.parts[-2] == self.target_id]
        role_files = [str(file) for file in files if file.parts[-2] in self.roles]
        all_files = [str(file) for file in files if file.parts[-2] == "all"]
        logger.debug(
            "Files discovered: {files}".format(
                files=host_files + role_files + all_files
            )
        )
        return host_files + role_files + all_files

    def parse_config(self) -> None:
        """
        Initial step in config parsing. Loops through applicable files and renders the
        contents from YAML through jinja2 and populates the self.mapping table with
        path and contents and populates self.file_paths table with filename and paths
        defined in that file (the latter is mostly for section matching if given a file
        name instead of a path).
        """
        for file in self._get_files():
            # skip platforms that don't match
            if "_" in file:
                # skip for services entirely
                if "service-id" in self.variables:
                    continue
                platform = self.variables["platform"]["os"]
                if (suffix := re.search("_(.*).yaml.j2", file)) and suffix.groups()[
                    0
                ] != platform:
                    logger.debug(
                        "Platform suffix for file {file} does not match device "
                        "platform {platform}, skipping".format(
                            file=file, platform=platform
                        )
                    )
                    continue
            # render the data using jinja2 with vars from self.variables
            env = jinja2.Environment(loader=jinja2.FileSystemLoader("/"))
            template = env.get_template(file)
            spec = YAML().load(template.render(self.variables))
            for path, content in spec.items():
                self.file_paths[str(Path(file).parts[-1])].append(path)
                self.mapping[path].append(content)

    def merge_paths(self):
        """
        If there are any paths that have multiple config elements we merge them here.
        This method relies on loading the contents into a pyangbind binding since that
        is easier than attempting a recursive merge on a complex JSON object. This
        method therefore relies on a binding module to be present and a translation
        between a path and a binding to use set under "merge-bindings" in settings.yaml.
        """
        found = False
        for path, config_list in self.mapping.items():
            if len(config_list) > 1:
                logger.info(
                    "More than one config element found for {path}, continuing "
                    "merge".format(path=path)
                )
                found = True
        if not found:
            logger.info("No paths have more than one config element, skipping merge")
            return

        if "merge-bindings" not in self.settings:
            logger.warning(
                "No merge bindings defined in settings.yaml, but path with more than "
                "one config element exists, one entry may overwrite the other"
            )
            return
        binding_translate = self.settings["merge-bindings"]
        import importlib
        from pyangbind.lib.serialise import pybindJSONDecoder  # type: ignore
        import pyangbind.lib.pybindJSON as pybindJSON  # type: ignore

        for path, config_list in self.mapping.items():
            if len(config_list) == 1:
                continue
            if path not in binding_translate:
                logger.warning(
                    "Path {path} has multiple entries but no binding mapping, one "
                    "entry may overwrite the other".format(path=path)
                )
                return
            binding = importlib.import_module(
                binding_translate[path]["binding"], package=None
            )
            binding_class = getattr(binding, binding_translate[path]["object"])
            binding_object = getattr(binding_class, binding_translate[path]["object"])()
            for content in config_list:
                pybindJSONDecoder.load_ietf_json(
                    content, None, None, obj=binding_object
                )
            self.mapping[path] = [
                json.loads(pybindJSON.dumps(binding_object, mode="ietf", indent=None))
            ]
            logger.info("Merge complete for path {path}".format(path=path))

    def build_packs(self) -> List[ConfigPack]:
        """
        Compile pack list. Creates head of list based on priorities defined in
        self.settings and appends unprioritized entries to that.
        """
        write_methods = self.settings["write-methods"]
        packs = [
            ConfigPack(
                path=path,
                original_content=dict(content[0]),
                content=content[0],
                write_method=write_methods.get(path, write_methods["default"]),
            )
            for priority_path in self.settings["priority"]
            for path, content in self.mapping.items()
            if path == priority_path
        ]
        if self.sections:
            packs = [
                pack
                for pack in packs
                for section in self.sections
                if section in pack.path
            ]
        logger.info(
            "Prioritized paths set as {paths}".format(
                paths=[pack.path for pack in packs]
            )
        )
        for path, content in self.mapping.items():
            write_method = write_methods.get(path, write_methods["default"])
            if path not in self.settings["priority"]:
                if self.sections:
                    for section in self.sections:
                        if section in path:
                            packs.append(
                                ConfigPack(
                                    path=path,
                                    original_content=dict(content[0]),
                                    content=content[0],
                                    write_method=write_method,
                                )
                            )
                else:
                    packs.append(
                        ConfigPack(
                            path=path,
                            original_content=dict(content[0]),
                            content=content[0],
                            write_method=write_method,
                        )
                    )
        if self.sections and not packs:
            logger.warning(
                "Could not find match for target {id} given section {sections} in "
                "configured paths or files {paths_and_files}, skipping".format(
                    id=self.target_id,
                    sections=self.sections,
                    paths_and_files=list(self.mapping.keys())
                    + list(self.file_paths.keys()),
                )
            )

        return packs
