from network_iac.connectors.gnmi import GnmiDevice  # type: ignore

device_object = GnmiDevice(hostname="jfk-spine05", ip="127.0.0.1")


def test_device_password():
    """
    Test that an admin password is fetched from the vault
    """
    assert "PASSWORD_USERNAME_admin" in device_object.vault.keys


def test_config_push():
    """
    Test that config push returns the correct values. Rather crude since it only does
    dry-run mode, but we don't have a hardware lab to use yet. Approximates a correct
    JSON payload by simply ensuring that the character count is > 1000.
    """
    push_results = device_object.push_config(
        method="replace", section=None, debug=False, dry_run=True
    )
    assert isinstance(push_results[0], str) and len(push_results[0]) > 1000
    assert not push_results[1]
