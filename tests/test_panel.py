"""Ověření tabulky a autorizace s minimálními doubles HA."""

import importlib
import sys
from types import ModuleType
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest


@pytest.fixture
def panel(monkeypatch):
    def module(name, **attrs):
        mod = ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    module("homeassistant")
    frontend = module("homeassistant.components.frontend")
    custom = module("homeassistant.components.panel_custom")
    ws = module(
        "homeassistant.components.websocket_api",
        websocket_command=lambda schema: lambda fn: fn,
        async_response=lambda fn: fn,
    )
    module("homeassistant.components", frontend=frontend, panel_custom=custom, websocket_api=ws)
    module("homeassistant.components.http", StaticPathConfig=object)
    module("homeassistant.core", callback=lambda fn: fn)
    registry = NS(async_get_entity_id=lambda *args: None)
    er = module("homeassistant.helpers.entity_registry", async_get=lambda hass: registry)
    module("homeassistant.helpers", entity_registry=er)
    imported = importlib.import_module("component_under_test.panel")
    yield imported
    sys.modules.pop("component_under_test.panel", None)


@pytest.mark.parametrize(
    "admin,domain,state",
    [
        (False, "synology_srm_extended", "loaded"),
        (True, "other", "loaded"),
        (True, "synology_srm_extended", "not_loaded"),
    ],
)
def test_client_table_rejects_unauthorized_or_unloaded(panel, admin, domain, state):
    entry = NS(domain=domain, state=NS(value=state), runtime_data=NS())
    hass = NS(config_entries=NS(async_get_entry=Mock(return_value=entry)))
    connection = NS(user=NS(id="test-user", is_admin=admin), send_error=Mock(), send_result=Mock())
    panel.websocket_clients(hass, connection, {"id": 1, "entry_id": "router"})
    connection.send_error.assert_called_once()
    connection.send_result.assert_not_called()
    connection.send_error.reset_mock()
    panel.websocket_resources(hass, connection, {"id": 2, "entry_id": "router"})
    connection.send_error.assert_called_once()
    connection.send_result.assert_not_called()


def test_table_returns_names_addresses_and_stale_status(panel):
    from srm.models import Client

    client = Client(
        "02:11:22:33:44:55",
        False,
        False,
        {"hostname": "Telefon", "ip_addr": "192.168.1.42", "password": "never-export"},
    )
    coordinator = NS(
        last_update_success=False,
        inventory=NS(current={client.mac: client}, hidden=set(), views={}),
        options={},
    )
    entry = NS(
        entry_id="router",
        domain="synology_srm_extended",
        state=NS(value="loaded"),
        runtime_data=NS(clients=coordinator),
    )
    hass = NS(config_entries=NS(async_get_entry=lambda eid: entry))
    connection = NS(user=NS(id="test-user", is_admin=True), send_error=Mock(), send_result=Mock())
    panel.websocket_clients(hass, connection, {"id": 1, "entry_id": "router"})
    connection.send_result.assert_called_once_with(
        1,
        {
            "available": False,
            "integration_version": "0.1.12",
            "view": None,
            "poll_interval": 30,
            "traffic_settings": {"source_unit": "unknown", "rx_direction": "unknown"},
            "clients": [
                {
                    "name": "Telefon",
                    "ip": "192.168.1.42",
                    "mac": client.mac,
                    "online": False,
                    "wireless": False,
                    "hidden": False,
                    "details": {"hostname": "Telefon", "ip_addr": "192.168.1.42"},
                    "tracker": {
                        "selected": False,
                        "entity_id": None,
                        "disabled": False,
                        "state": None,
                    },
                }
            ],
        },
    )


def test_table_reports_registered_disabled_tracker(panel):
    from srm.models import Client

    client = Client("02:11:22:33:44:55", True, True, {})
    registry = NS(
        async_get_entity_id=lambda *args: "device_tracker.telefon",
        async_get=lambda entity_id: NS(disabled_by="user"),
    )
    panel.er.async_get = lambda hass: registry
    coordinator = NS(
        last_update_success=True,
        inventory=NS(current={client.mac: client}, hidden=set(), views={}),
        options={"tracker_clients": [client.mac]},
    )
    entry = NS(
        entry_id="router",
        domain="synology_srm_extended",
        state=NS(value="loaded"),
        runtime_data=NS(clients=coordinator),
    )
    hass = NS(config_entries=NS(async_get_entry=lambda eid: entry), states=NS(get=lambda eid: None))
    connection = NS(user=NS(id="test-user", is_admin=True), send_error=Mock(), send_result=Mock())
    panel.websocket_clients(hass, connection, {"id": 1, "entry_id": "router"})
    tracker = connection.send_result.call_args.args[1]["clients"][0]["tracker"]
    assert tracker == {
        "selected": True,
        "entity_id": "device_tracker.telefon",
        "disabled": True,
        "state": None,
    }


@pytest.mark.parametrize("admin,known", [(False, True), (True, False), (True, True)])
async def test_visibility_requires_admin_and_known_client(panel, admin, known):
    from unittest.mock import AsyncMock

    mac = "02:11:22:33:44:55"
    clients = NS(inventory=NS(known={mac: "Test"} if known else {}), async_set_hidden=AsyncMock())
    entry = NS(
        domain="synology_srm_extended", state=NS(value="loaded"), runtime_data=NS(clients=clients)
    )
    hass = NS(config_entries=NS(async_get_entry=lambda eid: entry))
    connection = NS(user=NS(id="test-user", is_admin=admin), send_error=Mock(), send_result=Mock())
    await panel.websocket_client_visibility(
        hass, connection, {"id": 1, "entry_id": "router", "mac": mac, "hidden": True}
    )
    if admin and known:
        clients.async_set_hidden.assert_awaited_once_with(mac, True)
        connection.send_result.assert_called_once_with(1, {"hidden": True})
    else:
        clients.async_set_hidden.assert_not_awaited()
        connection.send_error.assert_called_once()


async def test_view_saved_for_authenticated_user_only(panel):
    from unittest.mock import AsyncMock

    clients = NS(async_set_view=AsyncMock())
    entry = NS(
        domain="synology_srm_extended", state=NS(value="loaded"), runtime_data=NS(clients=clients)
    )
    hass = NS(config_entries=NS(async_get_entry=lambda eid: entry))
    connection = NS(user=NS(is_admin=True, id="actual-user"), send_error=Mock(), send_result=Mock())
    view = {"sort": "signal", "filter": "online", "visibility": "visible", "descending": True}
    await panel.websocket_view(hass, connection, {"id": 1, "entry_id": "router", "view": view})
    clients.async_set_view.assert_awaited_once_with("actual-user", view)
    connection.send_result.assert_called_once_with(1, {"saved": True})
    connection.user.is_admin = False
    clients.async_set_view.reset_mock()
    await panel.websocket_view(hass, connection, {"id": 2, "entry_id": "router", "view": view})
    clients.async_set_view.assert_not_awaited()


@pytest.mark.parametrize("admin,known", [(False, True), (True, False), (True, True)])
async def test_wol_only_known_client_and_admin(panel, admin, known):
    from unittest.mock import AsyncMock

    mac = "02:11:22:33:44:55"
    entry = NS(
        domain="synology_srm_extended",
        state=NS(value="loaded"),
        runtime_data=NS(clients=NS(inventory=NS(known={mac: "PC"} if known else {}))),
    )
    hass = NS(
        config_entries=NS(async_get_entry=lambda eid: entry), async_add_executor_job=AsyncMock()
    )
    connection = NS(user=NS(is_admin=admin), send_error=Mock(), send_result=Mock())
    await panel.websocket_wol(hass, connection, {"id": 1, "entry_id": "router", "mac": mac})
    if admin and known:
        hass.async_add_executor_job.assert_awaited_once_with(panel.send_wol, mac)
        connection.send_result.assert_called_once_with(1, {"sent": True})
    else:
        hass.async_add_executor_job.assert_not_awaited()
        connection.send_error.assert_called_once()


def test_magic_packet_format(panel):
    from component_under_test.wol import magic_packet

    packet = magic_packet("02:11:22:33:44:55")
    assert len(packet) == 102
    assert packet == bytes.fromhex("ff" * 6 + "021122334455" * 16)
    with pytest.raises(ValueError):
        magic_packet("invalid")
