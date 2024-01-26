from ananke.struct.config import ConfigPack


def transform(pack: ConfigPack) -> ConfigPack:
    """
    Transforms necessary for NX-OS
    1) Remove "iana-if-type" namespace from interfaces. Pyangbind adds these but the
       device doesn't like them.
    2) Remove all config data from interfaces part of a port-channel in update mode.
       We need to use update mode since replace mode blows everything away and can take
       minutes for the configs to reconverge. In update mode we cannot add any config
       data (including status and description, which are allowed over CLI) to interfaces
       that are part of a port channel. This means changes to status or description must
       be done manually or with a replace call (which involves an outage).
    """
    if pack.path == "openconfig:/interfaces":
        interfaces = pack.content["openconfig-interfaces:interface"]
        for index, interface in enumerate(interfaces):
            # remove namespace from interface type
            if "type" in interface["config"]:
                interface["config"]["type"] = interface["config"]["type"].replace(
                    "iana-if-type:l2vlan", "l2vlan"
                )
            # remove all config except for aggr ID for interfaces in port channel if
            # write mode is update
            if "openconfig-if-ethernet:ethernet" in interface:
                if pack.write_method == "replace":
                    continue
                aggr_id = interface["openconfig-if-ethernet:ethernet"]["config"][
                    "openconfig-if-aggregate:aggregate-id"
                ]
                interfaces[index] = {
                    "name": interface["name"],
                    "openconfig-if-ethernet:ethernet": {
                        "config": {"openconfig-if-aggregate:aggregate-id": aggr_id}
                    },
                }
    return pack
