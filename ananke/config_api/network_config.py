import os
import ruamel.yaml  # type: ignore
import json
import logging
from typing import Any, Optional, Tuple, Union
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


class RepoInterface:
    """
    Class for interacting with a repo and populating data in a readable format.

    NetworkConfig inherits from here since it always needs it, but this class can be
    instantiated independently if other applications need to read from the repo outside
    of NetworkConfig
    """

    def __init__(
        self,
        branch: Union[bool, str] = True,
        repo: Optional[Union[GitLabRepo, LocalRepo]] = None,
    ):
        if not repo:
            self.repo = self._populate_repo(branch)
        else:
            self.repo = repo
        self.yaml = self._create_yaml_object()
        self.repo_objects = self.repo.list_objects()
        self.repo_devices = set(
            [
                object.parts[-2]
                for object in self.repo_objects
                if object.suffix == ".j2" and object.parts[0] == "devices"
            ]
        )
        self.repo_roles = set(
            [
                object.parts[-2]
                for object in self.repo_objects
                if object.suffix == ".j2" and object.parts[0] == "roles"
            ]
        )

    def _populate_settings(self) -> Any:
        """
        Get settings from ANANKE_CONFIG/settings.yaml
        """

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

    def get_path_and_content(self, file_path: str) -> Tuple[str, Any]:
        """
        Fetches YAML content from GitLab and returns the key of the file along with the
        content from that key.

        The assumption is that files that this software interacts with are only ever
        single key, and the yang_path comes in handy in some applications for figuring
        out which data model a particular device is using.
        """
        content_raw = self.repo.get_file(path=file_path)
        content = self.yaml.load(content_raw.decode())
        keys = list(content.keys())
        if len(keys) > 1:
            logger.warning(
                f"File contains more than one key: {keys}. Only the first "
                "key will be used"
            )
        return keys[0], content

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


class NetworkConfig(RepoInterface):
    """
    Base class with shared network functions, allows for optional repo object to
    be passed in in case we are orchestrating several changes at once and want them on
    the same branch, etc.
    """

    def __init__(
        self,
        file_path: str,
        repo: Optional[Union[GitLabRepo, LocalRepo]] = None,
    ):
        super().__init__(repo=repo)
        self.file_path = file_path
        self.yang_path, self.content = self.get_path_and_content(file_path)
        if not self.repo:
            raise AttributeError("Repo not provided and failed to instantiate")
        logger.debug(
            "YANG path: {yang_path}\nContent: {content}".format(
                yang_path=self.yang_path, content=self.content
            )
        )

    def populate_binding(self, binding_object: Any):
        """
        Populates class binding with dict content fetched from repo
        """
        from pyangbind.lib.serialise import pybindJSONDecoder  # type: ignore

        pybindJSONDecoder.load_ietf_json(
            self.content[self.yang_path], None, None, obj=binding_object
        )
        logger.debug(
            f"Populating pyangbind object for config content: {binding_object}"
        )
        self.binding = binding_object

    def export_binding(self) -> Any:
        """
        We need to be able to export the content of a changed schema to run our tests,
        so we split it out in a separate function here
        """
        import pyangbind.lib.pybindJSON as pybindJSON  # type: ignore

        ietf_json = pybindJSON.dumps(self.binding, mode="ietf", indent=None)
        exported = {self.yang_path: json.loads(ietf_json)}
        logger.debug(
            "Exporting JSON from binding: {exported}".format(exported=exported)
        )
        return exported

    def commit_file(
        self,
        author_name: str = "DV Network Configurator",
        author_email: str = "network@doubleverify.com",
        commit_message: str = "Automated commit",
    ) -> None:
        """
        Commit changes to file. Accepts optional branch name, but automatically
        generates one if not given.
        """
        yaml_string = StringIO()
        if hasattr(self, "binding"):
            new_content = self.export_binding()
            # skip empty commits
            if self.content == new_content:
                return
        else:
            new_content = self.content
        self.yaml.dump(new_content, yaml_string)
        logger.info("Committing file {path}".format(path=self.file_path))
        logger.debug("File contents {contents}".format(contents=yaml_string.getvalue()))
        self.repo.update_file(
            path=self.file_path,
            content=yaml_string.getvalue(),
            author_email=author_email,
            author_name=author_name,
            commit_message=commit_message,
        )
