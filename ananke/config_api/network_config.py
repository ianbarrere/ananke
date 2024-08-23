import os
import ruamel.yaml  # type: ignore
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Tuple, Union, Optional, Dict
from io import StringIO
from ananke.struct.repo import GitLabRepo, LocalRepo  # type: ignore
from ananke.struct.vault import Vault  # type: ignore

REPO_TARGET = os.environ.get("ANANKE_REPO_TARGET")
CONFIG_DIR = os.environ.get("ANANKE_CONFIG")

logger = logging.getLogger(__name__)


class NonAliasingRTRepresenter(ruamel.yaml.representer.RoundTripRepresenter):
    """
    Ruamel by default uses anchors and aliases when outputting YAML. We want to avoid
    that and always have explicit structures, so we customize the Representer here.
    """

    def ignore_aliases(self, data):
        return True


@dataclass
class RepoConfigSection:
    """
    Object representation of a config file from repo
    """

    hostname: str
    path: Optional[str]
    content: Optional[Any]
    changed: bool = False
    new_file: bool = False
    binding: Any = None

    def populate_binding(self, binding_object: Any, overwrite: bool = False):
        """
        Populates class binding with dict content fetched from repo
        """
        if not overwrite:
            from pyangbind.lib.serialise import pybindJSONDecoder  # type: ignore

            pybindJSONDecoder.load_ietf_json(
                list(self.content.values())[0], None, None, obj=binding_object
            )
            logger.debug(
                "Populating binding object with config content: {}".format(self.content)
            )
        logger.debug("Assigning binding: {}".format(binding_object))
        self.binding = binding_object

    def export_binding(self) -> Any:
        """
        We need to be able to export the content of a changed schema to run our tests,
        so we split it out in a separate function here
        """
        import pyangbind.lib.pybindJSON as pybindJSON  # type: ignore

        ietf_json = pybindJSON.dumps(self.binding, mode="ietf", indent=None)
        exported = {self.path: json.loads(ietf_json)}
        logger.debug(
            "Exporting JSON from binding: {exported}".format(exported=exported)
        )
        if exported != self.content:
            self.changed = True
        self.content = exported


class RepoConfigInterface:
    """
    Class for interacting with a repo and populating data in a readable format.

    NetworkConfig inherits from here since it always needs it, but this class can be
    instantiated independently if other applications need to read from the repo outside
    of NetworkConfig
    """

    def __init__(
        self,
        branch: Union[bool, str] = False,
    ):
        self.repo = self._populate_repo(branch)
        self.yaml = self._create_yaml_object()
        self.content_map: Dict[str, RepoConfigSection] = {}
        self.repo_objects = self.repo.list_objects()
        self.repo_devices = set(
            [
                object.parts[-2]
                for object in self.repo_objects
                if object.suffix in [".j2", ".yaml"] and object.parts[0] == "devices"
            ]
        )
        self.repo_roles = set(
            [
                object.parts[-2]
                for object in self.repo_objects
                if object.suffix in [".j2", ".yaml"] and object.parts[0] == "roles"
            ]
        )

    def _create_yaml_object(self) -> ruamel.yaml.YAML:
        """
        Setup a global YAML object for use in reading and writing
        """
        yaml = ruamel.yaml.YAML(typ="jinja2")
        yaml.Representer = NonAliasingRTRepresenter
        yaml.preserve_quotes = True
        yaml.explicit_start = True
        yaml.indent(offset=2, sequence=4)
        return yaml

    def _populate_vault(self) -> None:
        """
        Build and populate vault instance for secrets
        """
        if not CONFIG_DIR:
            raise ValueError(
                "ANANKE_CONFIG environment variable must be set to build vault. To "
                "run without vault set the ANANKE_CONFIG_PAT environment variable."
            )
        vault_secret = os.environ.get("ANANKE_VAULT_SECRET")
        if not vault_secret:
            raise ValueError("ANANKE_VAULT_SECRET env var must be set")
        with open(f"{CONFIG_DIR}/settings.yaml") as settings_file:
            settings = ruamel.yaml.YAML().load(settings_file.read())
        self.vault = Vault(
            vault_role_id=settings["vault"]["role-id"],
            vault_secret=os.environ.get("ANANKE_VAULT_SECRET"),
            url=settings["vault"]["url"],
            mount_point=settings["vault"]["mount-point"],
            paths=["network/pipeline"],
        )

    def _populate_repo(self, branch: Union[bool, str]) -> Union[GitLabRepo, LocalRepo]:
        """
        Populates self.repo with an instantiated GitLabRepo/LocalRepo instance.

        If REPO_TARGET is only numbers we assume it's a GitLab project ID and therefore
        instantiate a GitLabRepo instance, otherwise we assume it's a path and use
        LocalRepo.
        """
        if not REPO_TARGET:
            raise ValueError(
                "ANANKE_REPO_TARGET env var must be set to either a "
                "local git repo path or GitLab project ID"
            )
        if not os.environ.get("ANANKE_CONFIG_PAT"):
            self._populate_vault()
            config_pat = self.vault.keys.get("ANANKE_CONFIG_PAT")
        else:
            config_pat = os.environ["ANANKE_CONFIG_PAT"]
        if not config_pat:
            raise ValueError(
                "Could not get project access token from env var "
                "ANANKE_CONFIG_PAT or vault key ANANKE_CONFIG_PAT"
            )
        if REPO_TARGET.isnumeric():
            logger.info(
                "Initializing GitLab repo for project {target}".format(
                    target=REPO_TARGET
                )
            )
            return GitLabRepo(
                project_id=REPO_TARGET,
                token=config_pat,
                branch=branch,
            )
        else:
            logger.info(
                "Initializing local repo for path {target}".format(target=REPO_TARGET)
            )
            return LocalRepo(REPO_TARGET, branch=branch)

    def populate_content_map(self, file_path: str) -> RepoConfigSection:
        """
        Fetches YAML content from GitLab and populates RepoConfigSection object in
        content_map along with returning the RepoConfigSection.

        The assumption is that files that this software interacts with are only ever
        single key, and the yang_path comes in handy in some applications for figuring
        out which data model a particular device is using.
        """
        if file_path in self.content_map.keys():
            logger.info(
                "Content map already populated for {}, skipping".format(file_path)
            )
            return self.content_map[file_path]
        hostname = Path(file_path).parts[-2]
        content_raw = self.repo.get_file(path=file_path, create=True)
        if not content_raw:
            content = self.content_map[file_path] = RepoConfigSection(
                hostname=hostname, path=None, content=None, new_file=True
            )
        else:
            content = self.yaml.load(content_raw.decode())
            keys = list(content.keys())
            if len(keys) > 1:
                logger.warning(
                    f"File contains more than one key: {keys}. Only the first "
                    "key will be used as path"
                )
            self.content_map[file_path] = RepoConfigSection(
                hostname=hostname, path=keys[0], content=content
            )
        return self.content_map[file_path]

    def get_device_vars(self, file_path: str) -> Any:
        """
        Get contents of vars.yaml file for a given host
        """
        if file_path.split("/")[-1] not in self.repo_devices:
            raise ValueError(f"Host path {file_path} not found")
        content_raw = self.repo.get_file(path=f"devices/{file_path}/vars.yaml")
        variables = self.yaml.load(content_raw.decode())
        logger.debug(
            "Device vars for {path}:\n\n{vars}".format(path=file_path, vars=variables)
        )
        return variables

    def get_settings(self) -> Any:
        """
        Get contents of vars.yaml file for a given host
        """
        content_raw = self.repo.get_file(path=f"settings.yaml")
        settings = self.yaml.load(content_raw.decode())
        logger.debug("Settings: {}".format(settings))
        return settings

    def commit(
        self,
        commit_message: str = "Automated commit",
        author_name: str = "DV Network Configurator",
        author_email: str = "network@doubleverify.com",
    ) -> None:
        actions = []
        for file_path, config_object in self.content_map.items():
            yaml_string = StringIO()
            # skip empty commits
            if not config_object.changed:
                continue
            if not config_object.new_file and Path(file_path).parts[-1] != "vars.yaml":
                self.yaml.dump(config_object.content, yaml_string)
            # need non-j2 YAML for new files and vars.yaml
            else:
                yaml = ruamel.yaml.YAML()
                yaml.Representer = NonAliasingRTRepresenter
                yaml.preserve_quotes = True
                yaml.explicit_start = True
                yaml.indent(offset=2, sequence=4)
                yaml.dump(config_object.content, yaml_string)
            content = yaml_string.getvalue()
            actions.append(
                {
                    "file_path": file_path,
                    "action": "update" if not config_object.new_file else "create",
                    "content": content,
                    "author_email": author_email,
                    "author_name": author_name,
                }
            )
        # clear content map after a commit
        self.content_map.clear()
        if not actions:
            return
        self.repo.bulk_commit(
            commit_message=commit_message,
            actions=actions,
        )
