"""Konfigurace nesmí přijmout URL s přihlašovacími údaji nebo vloženou cestou."""

import pytest
from srm.connection import base_url, normalize_host


@pytest.mark.parametrize(
    "value", ["https://router", "user:pass@router", "router/path", "router?x=1", ""]
)
def test_bad_host(value):
    with pytest.raises(ValueError):
        normalize_host(value)


def test_ip_and_hostname():
    assert normalize_host("Router.Local.") == "router.local"
    assert base_url("[2001:db8::1]", 8001, True) == "https://[2001:db8::1]:8001"
    assert base_url("192.0.2.1", 8000, False) == "http://192.0.2.1:8000"


@pytest.mark.parametrize("port", [0, 65536, True, "8001"])
def test_port_validation(port):
    with pytest.raises(ValueError):
        base_url("router", port, True)
