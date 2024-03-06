from ananke.struct.config import ConfigPack


def transform(pack: ConfigPack) -> ConfigPack:
    """
    Transforms necessary for Megaport
    """
    if pack.path.startswith("https://api-staging.megaport.com/v3/product/vxc"):
        # Need to remove all bEnd details before sending since we don't own the bEnd
        del pack.content["bEndVlan"]
    return pack
