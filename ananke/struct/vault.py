import hvac  # type: ignore
from typing import Dict, List


class Vault:
    """
    A simple Hashicorp Vault integration. Sets up the vault and reads keys from the
    supplied paths at the supplied mount point.
    """

    def __init__(
        self,
        paths: List[str],
        mount_point: str,
        url: str,
        vault_role_id: str,
        vault_secret: str,
    ) -> None:
        self.client = hvac.Client(url=url)
        self.client.auth.approle.login(
            role_id=vault_role_id,
            secret_id=vault_secret,
        )
        if not self.client.is_authenticated():
            raise RuntimeError("Unable to authenticate to vault")

        self.keys = self.read_keys(paths, mount_point)

    def read_keys(self, paths: List[str], mount_point: str) -> Dict[str, str]:
        """
        Read passwords from vault
        """
        joined: Dict[str, str] = {}
        for path in paths:
            joined = (
                joined
                | self.client.secrets.kv.v2.read_secret_version(
                    mount_point=mount_point,
                    path=path,
                    raise_on_deleted_version=False,
                )["data"]["data"]
            )
        return joined
