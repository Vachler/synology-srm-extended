"""Syntetické scénáře přítomnosti a stability identity."""

import pytest
from srm.errors import ResponseError
from srm.models import Inventory, boolean, normalize_mac, parse_clients, summarize

MAC = "02:11:22:33:44:55"


def devices(**extra):
    return {"devices": [{"mac": MAC, "is_online": True, **extra}]}


@pytest.mark.parametrize(
    "value", [MAC.upper(), "021122334455", "02-11-22-33-44-55", "0211.2233.4455"]
)
def test_mac_formats(value):
    assert normalize_mac(value) == MAC


@pytest.mark.parametrize("value", [None, "", "ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00", "hostname"])
def test_bad_mac(value):
    assert normalize_mac(value) is None


@pytest.mark.parametrize(
    "value,expected",
    [
        (False, False),
        ("false", False),
        ("0", False),
        ("true", True),
        (1, True),
        (None, None),
        ("online", None),
    ],
)
def test_explicit_booleans(value, expected):
    assert boolean(value) is expected


def test_no_ip_identity_and_no_secrets_in_attributes():
    first = parse_clients(devices(ip_addr="192.0.2.1", hostname="První", password="secret"))
    second = parse_clients(devices(ip_addr="192.0.2.2", hostname="Druhý"))
    assert first.keys() == second.keys() == {MAC}
    assert "password" not in first[MAC].attributes
    assert second[MAC].attributes["ip_addr"] == "192.0.2.2"


def test_inventory_keeps_offline_and_absent_but_not_stale_presence():
    inventory = Inventory()
    inventory.update(parse_clients(devices(hostname="Telefon")), create=True, selected={MAC})
    inventory.update(parse_clients(devices(is_online=False)), create=True, selected={MAC})
    assert MAC in inventory.monitored
    assert inventory.current[MAC].online is False
    inventory.update({}, create=True, selected={MAC})
    assert MAC in inventory.monitored
    assert MAC not in inventory.current
    restored = Inventory()
    restored.restore(inventory.serialize())
    assert restored.monitored == {MAC}
    assert restored.current == {}
    assert restored.known[MAC] == "Telefon"


def test_only_explicit_selection_creates_entities():
    inventory = Inventory()
    inventory.update(parse_clients(devices(is_online=False)), create=True, selected=set())
    assert not inventory.monitored
    assert MAC in inventory.known
    inventory.update(parse_clients(devices()), create=False, selected={MAC})
    assert not inventory.monitored
    inventory.update(parse_clients(devices()), create=True, selected={MAC})
    assert inventory.monitored == {MAC}
    inventory.update(parse_clients(devices()), create=True, selected=set())
    assert not inventory.monitored


@pytest.mark.parametrize("value", [{}, [], {"devices": None}, {"devices": [{"mac": ""}]}])
def test_invalid_snapshot_is_not_empty_network(value):
    with pytest.raises(ResponseError):
        parse_clients(value)


def test_empty_snapshot_is_valid():
    assert summarize(parse_clients({"devices": []}))["online"] == 0


def test_counts_are_online_only_and_unknown_is_not_zero():
    data = {
        "devices": [
            {"mac": MAC, "is_online": True, "is_wireless": False, "is_guest": False},
            {"mac": "02:11:22:33:44:56", "is_online": False, "is_wireless": True, "is_guest": True},
        ]
    }
    summary = summarize(parse_clients(data))
    assert summary == {"known": 2, "online": 1, "offline": 1, "wifi": 0, "lan": 1, "guest": 0}
    data["devices"][0].pop("is_online")
    summary = summarize(parse_clients(data))
    assert summary["online"] is None
    assert summary["wifi"] is None


def test_unknown_wireless_does_not_count_as_lan():
    summary = summarize(parse_clients(devices()))
    assert summary["online"] == 1
    assert summary["lan"] is None


def test_conflicting_duplicates_fail_closed():
    data = devices()
    data["devices"].append({"mac": MAC, "is_online": False})
    with pytest.raises(ResponseError):
        parse_clients(data)


def test_raw_metrics_preserved_without_assumed_units():
    client = parse_clients(
        devices(
            signalstrength=86,
            transferRXRate=1234,
            transferTXRate=4321,
            current_rate=1200,
            wifi_ssid="Test",
            password="secret",
        )
    )[MAC]
    assert client.attributes["signalstrength"] == 86
    assert client.attributes["transferRXRate"] == 1234
    assert client.attributes["transferTXRate"] == 4321
    assert "password" not in client.attributes


def test_hidden_inventory_restores_and_accepts_old_format():
    inventory = Inventory()
    inventory.hidden.add(MAC)
    restored = Inventory()
    restored.restore(inventory.serialize())
    assert restored.hidden == {MAC}
    old = Inventory()
    old.restore({"known": {MAC: "Test"}, "monitored": []})
    assert not old.hidden
