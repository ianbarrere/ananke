from typing import Optional, List, Any
from ananke.config_api.network_config import RepoConfigInterface, RepoConfigSection
from ananke.bindings.oc_network_instance import network_instances


def create_neighborship(host_a: str, host_b: str):
    """
    Sample workflow
    """
    rci = RepoConfigInterface(branch=True)
    rci.populate_content_map(f"path/to/{host_a}/bgp.yaml.j2")
    rci.populate_content_map(f"path/to/{host_b}/bgp.yaml.j2")
    OcBgpNeighbor(
        rcs=rci.content_map[f"path/to/{host_a}/bgp.yaml.j2"],
        address="1.2.3.4",
        description="Neighbor B",
        asn=64512,
    )
    OcBgpNeighborNoBind(
        rcs=rci.content_map[f"path/to/{host_b}/bgp.yaml.j2"],
        address="1.2.3.3",
        description="Neighbor A",
        asn=64512,
    )
    rci.commit(commit_message="Create BGP neighborship")
    pr_url = rci.repo.create_pr("I just created a BGP neighborship")
    print("Go here to approve: " + pr_url)


class OcBgpNeighbor:
    """
    Object for interacting with BGP neighbor config with binding
    """

    def __init__(
        self, rcs: RepoConfigSection, address: str, description: str, asn: int
    ):
        """
        Here we populate our binding object, make our changes, and then export the
        binding back to JSON/dictionary to be ready for commit.
        """
        ni = network_instances.network_instances()
        rcs.populate_binding(binding_object=ni)
        self.binding = rcs.binding
        self.default = self.binding.network_instance["DEFAULT"]
        self.add(address, description, asn)
        rcs.export_binding()

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


class OcBgpNeighborNoBind:
    """
    Object for interacting with BGP neighbor config without binding
    """

    def __init__(
        self, rcs: RepoConfigSection, address: str, description: str, asn: int
    ):
        """
        Here we skip the rcs.populate_binding() step and instead just refer directly
        to the config dict in rcs.content
        """
        ni = rcs.content["openconfig:/network-instances"][
            "openconfig-network-instance:network-instance"
        ]
        default_index = self.get_yang_list_element(
            yang_list=ni, key="name", match="default"
        )
        self.default = ni[default_index]
        self.add(address, description, asn)

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
