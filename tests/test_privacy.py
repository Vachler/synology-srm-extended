"""Tajemství se mohou skrývat v klíčích, seznamech i JSON řetězcích."""

import json

from srm.privacy import catalog_summary, response_shape


def test_secrets_are_removed_recursively_including_keys():
    raw = {
        "password": "PASS_SECRET",
        "SID": "SID_SECRET",
        "SynoToken": "TOKEN_SECRET",
        "cookies": {"id": "COOKIE_SECRET"},
        "username": "USERNAME_SECRET",
        "devices": [
            {
                "mac": "02:11:22:33:44:55",
                "hostname": "PRIVATE_NAME",
                "ip_addr": "192.0.2.123",
                "wifi_ssid": "PRIVATE_SSID",
            }
        ],
        "PRIVATE_KEY_NAME": {"network": '{"password":"NESTED_SECRET"}'},
        "cpu": {"user_load": 10},
        "numeric_password": 123456789,
    }
    rendered = json.dumps(response_shape(raw))
    for secret in (
        "PASS_SECRET",
        "SID_SECRET",
        "TOKEN_SECRET",
        "COOKIE_SECRET",
        "USERNAME_SECRET",
        "02:11:22:33:44:55",
        "PRIVATE_NAME",
        "192.0.2.123",
        "PRIVATE_SSID",
        "PRIVATE_KEY_NAME",
        "NESTED_SECRET",
        "123456789",
    ):
        assert secret not in rendered
    assert response_shape(raw)["cpu"]["user_load"] == 10


def test_unknown_string_values_are_never_exported_even_under_known_keys():
    assert response_shape({"model": "PERSONAL_ROUTER", "status": "SECRET"}) == {
        "model": "<string>",
        "status": "<string>",
    }


def test_bounded_shape_and_nonfinite_values():
    result = response_shape({"devices": [{}] * 100, "rx": float("nan")})
    assert len(result["devices"]["__examples__"]) == 3
    assert result["rx"] == "<number>"
    json.dumps(result, allow_nan=False)


def test_catalog_is_allowlisted():
    assert catalog_summary(
        {
            "SECRET_API_NAME": {"minVersion": 1},
            "SYNO.Core.Network.NSM.Device": {"minVersion": 1, "maxVersion": 5, "path": "SECRET"},
        }
    ) == {"SYNO.Core.Network.NSM.Device": {"minVersion": 1, "maxVersion": 5}}


def test_technical_keys_and_diverse_examples_without_private_values():
    raw = {"eth_ports": [{"link_status": "up", "link_speed": 1000, "node_name": "SECRET_NODE"}]}
    shape = response_shape(raw)
    assert shape["eth_ports"]["__examples__"][0]["link_speed"] == 1000
    assert "SECRET_NODE" not in json.dumps(shape)
    clients = [{"is_online": True, "signalstrength": index} for index in range(8)]
    clients.append({"is_online": False, "ip6_addr": ["SECRET_IP"]})
    examples = response_shape(clients)["__examples__"]
    assert len(examples) <= 6
    assert any(example["is_online"] is False for example in examples)
    assert "SECRET_IP" not in json.dumps(examples)
