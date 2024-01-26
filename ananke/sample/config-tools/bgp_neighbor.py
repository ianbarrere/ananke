from typing import Optional, List, Any
from ananke.config_api.network_config import NetworkConfig
from ananke.struct.repo import GitLabRepo
from ananke.bindings.oc_network_instance import network_instances


class OcBgpNeighbor(NetworkConfig):
    """
    Object for interacting with BGP neighbor config with binding
    """

    def __init__(
        self,
        file_path: str,
        repo: Optional[GitLabRepo] = None,
    ):
        self.file_path = file_path
        super().__init__(
            file_path=self.file_path,
            repo=repo,
        )
        ni = network_instances.network_instances()
        self.populate_binding(binding_object=ni)
        self.default = ni.binding.network_instance["DEFAULT"]

    def add(self, address: str, description: str, asn: str) -> None:
        """
        Extremely simple example of a BGP neighbor tool
        """

        neighbors = self.default.protocols.protocol["BGP BGP"].bgp.neighbors.neighbor
        if address in neighbors:
            peer = neighbors[address]
        else:
            peer = neighbors.add(address)
        peer.config.neighbor_address = address
        peer.config.description = description
        peer.config.peer_as = asn


class OcBgpNeighborNoBind(NetworkConfig):
    """
    Object for interacting with BGP neighbor config without binding
    """

    def __init__(
        self,
        file_path: str,
        repo: Optional[GitLabRepo] = None,
    ):
        """
        Here we skip the self.populate_bindings() step and instead just refer directly
        to the config dict in self.content
        """
        self.file_path = file_path
        super().__init__(
            file_path=self.file_path,
            repo=repo,
        )
        ni = self.content["openconfig:/network-instances"][
            "openconfig-network-instance:network-instance"
        ]
        default_index = self.get_yang_list_element(
            yang_list=ni, key="name", match="default"
        )
        self.defaul = ni[default_index]

    @staticmethod
    def get_yang_list_element(
        yang_list: List[Any], key: Any, match: Any
    ) -> Optional[int]:
        """
        A common problem with YANG lists is trying to find an element within the list in
        order to update it. This same pattern needs to be used all over the place so we
        define a generic one here.
        Args:
            yang_list: A YANG list
            key: Not necessarily the YANG key, but the element within the list that we
                want to compare against
            match: The match criteria that we compare with the key
        Returns:
            Either the index of the list with our desired element or None if not found
        """
        target_index = next(
            (index for index, item in enumerate(yang_list) if item[key] == match),
            None,
        )
        return target_index

    def add(self, address: str, description: str, asn: str) -> None:
        """
        Extremely simple example of a BGP neighbor tool
        """
        protocols = self.default["protocols"]["protocol"]
        bgp_index = self.get_yang_list_element(
            yang_list=protocols, key="identifier", match="BGP"
        )
        bgp = protocols[bgp_index]
        neighbors = bgp["bgp"]["neighbors"]["neighbor"]
        neighbor = {
            "neighbor-address": address,
            "config": {
                "peer-as": asn,
                "description": description,
            },
        }
        neighbors.append(neighbor)
