from struct.config import Config, CONFIG_DIR  # type: ignore

config_object = Config(hostname="jfk-spine05")


def test_device_roles():
    """
    Test that the correct role(s) are applied to the device
    """
    assert config_object.roles == ["spine"]


def test_variables():
    """
    Test that the variables object has a roughly correct structure
    """
    assert (
        "vault" in config_object.variables["vars"]
        and "local" in config_object.variables["vars"]
    )


def test_packs():
    """
    Test that config packs is non-zero list and that each model in each element
    has a roughly correct path associated with it
    """
    assert len(config_object.packs) > 0
    for pack in config_object.packs:
        assert "openconfig" in pack[0] or "System" in pack[0]


def test_file_paths():
    """
    Test that the paths returned are in the correct order. This is important to ensure
    correct variable inheritance and overriding.
    """
    assert config_object._get_paths() == [
        f"{CONFIG_DIR}/share/all/",
        f"{CONFIG_DIR}/share/spine/",
        f"{CONFIG_DIR}/devices/jfk-spine05/",
    ]
