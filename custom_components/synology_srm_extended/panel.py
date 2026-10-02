"""Tabulka klientů v přihlášeném rozhraní Home Assistant."""

from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .resources import mesh_nodes
from .srm.models import CLIENT_FIELDS, RAW_METRIC_FIELDS, normalize_mac
from .wol import send_wol

URL = "/synology_srm_extended/clients-0.1.12.js"


def panel_path(entry_id):
    return f"synology-clients-{entry_id}"


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/resources", vol.Required("entry_id"): str}
)
@callback
def websocket_resources(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Dostupné správci HA.")
        return
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    runtime = getattr(entry, "runtime_data", None)
    if entry is None or entry.domain != DOMAIN or runtime is None or entry.state.value != "loaded":
        connection.send_error(msg["id"], "not_found", "Integrace není načtená.")
        return
    connection.send_result(
        msg["id"],
        {
            "history": list(runtime.readings.history),
            "mesh": mesh_nodes(runtime.readings.data or {}, runtime.clients.inventory.current),
        },
    )


async def async_setup_panel(hass):
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL, str(Path(__file__).parent / "frontend" / "clients.js"), False)]
    )
    websocket_api.async_register_command(hass, websocket_clients)
    websocket_api.async_register_command(hass, websocket_client_visibility)
    websocket_api.async_register_command(hass, websocket_view)
    websocket_api.async_register_command(hass, websocket_wol)
    websocket_api.async_register_command(hass, websocket_resources)
    # Modul se načte i bez otevření samostatného panelu: používá jej detail senzoru.
    hass.data[frontend.DATA_EXTRA_MODULE_URL].add(URL)


async def async_register_panel(hass, entry):
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=panel_path(entry.entry_id),
        webcomponent_name="synology-srm-clients-v0112",
        sidebar_title=None,
        sidebar_icon="mdi:router-network",
        module_url=URL,
        config={"entry_id": entry.entry_id},
        require_admin=True,
    )
    entry.async_on_unload(lambda: frontend.async_remove_panel(hass, panel_path(entry.entry_id)))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/clients",
        vol.Optional("entry_id"): str,
    }
)
@callback
def websocket_clients(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Tabulka je dostupná správci HA.")
        return
    if "entry_id" in msg:
        entry = hass.config_entries.async_get_entry(msg["entry_id"])
    else:
        entries = hass.config_entries.async_entries(DOMAIN)
        entry = entries[0] if len(entries) == 1 else None
    runtime = getattr(entry, "runtime_data", None)
    if entry is None or entry.domain != DOMAIN or runtime is None or entry.state.value != "loaded":
        connection.send_error(msg["id"], "not_found", "Integrace routeru není načtená.")
        return
    coordinator = runtime.clients
    readings = getattr(runtime, "readings", None)
    mesh_names = {
        str(node["id"]): node["name"]
        for node in mesh_nodes(getattr(readings, "data", None) or {}, coordinator.inventory.current)
        if node["id"] is not None and node["name"]
    }
    registry = er.async_get(hass)

    def tracker_info(mac):
        entity_id = registry.async_get_entity_id(
            "device_tracker", DOMAIN, f"{entry.entry_id}_{mac}_presence"
        )
        entity = registry.async_get(entity_id) if entity_id else None
        state = hass.states.get(entity_id) if entity_id else None
        return {
            "selected": mac in coordinator.options.get("tracker_clients", []),
            "entity_id": entity_id,
            "disabled": bool(entity and entity.disabled_by),
            "state": state.state if state else None,
        }

    connection.send_result(
        msg["id"],
        {
            "available": coordinator.last_update_success,
            "integration_version": "0.1.12",
            "view": coordinator.inventory.views.get(connection.user.id),
            "poll_interval": coordinator.options.get("poll_interval", 30),
            "traffic_settings": {
                "source_unit": coordinator.options.get("traffic_source_unit", "unknown"),
                "rx_direction": coordinator.options.get("traffic_rx_direction", "unknown"),
            },
            "clients": [
                {
                    "name": client.name,
                    "ip": client.attributes.get("ip_addr"),
                    "mac": client.mac,
                    "online": client.online,
                    "wireless": client.wireless,
                    "hidden": client.mac in coordinator.inventory.hidden,
                    "tracker": tracker_info(client.mac),
                    "details": {
                        **{
                            key: value
                            for key, value in client.attributes.items()
                            if key in CLIENT_FIELDS + RAW_METRIC_FIELDS
                        },
                        **(
                            {"mesh_node_name": mesh_names[str(client.attributes["mesh_node_id"])]}
                            if str(client.attributes.get("mesh_node_id")) in mesh_names
                            else {}
                        ),
                    },
                }
                for client in sorted(
                    coordinator.inventory.current.values(),
                    key=lambda client: client.name.casefold(),
                )
            ],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/client_visibility",
        vol.Required("entry_id"): str,
        vol.Required("mac"): str,
        vol.Required("hidden"): bool,
    }
)
@websocket_api.async_response
async def websocket_client_visibility(hass, connection, msg):
    """Skryje klienta pouze v seznamu integrace; nevolá zápisové API SRM."""
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Změna je dostupná správci HA.")
        return
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    runtime = getattr(entry, "runtime_data", None)
    if entry is None or entry.domain != DOMAIN or runtime is None or entry.state.value != "loaded":
        connection.send_error(msg["id"], "not_found", "Integrace routeru není načtená.")
        return
    mac = normalize_mac(msg["mac"])
    if mac is None or mac not in runtime.clients.inventory.known:
        connection.send_error(msg["id"], "not_found", "Klient není známý této integraci.")
        return
    try:
        await runtime.clients.async_set_hidden(mac, msg["hidden"])
    except Exception:
        connection.send_error(msg["id"], "save_failed", "Změnu se nepodařilo uložit.")
        return
    connection.send_result(msg["id"], {"hidden": msg["hidden"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/view",
        vol.Required("entry_id"): str,
        vol.Required("view"): {
            vol.Required("sort"): vol.In(["name", "state", "ip", "mac", "network", "signal"]),
            vol.Required("filter"): vol.In(["all", "online", "offline"]),
            vol.Required("visibility"): vol.In(["visible", "hidden", "all"]),
            vol.Required("descending"): bool,
        },
    }
)
@websocket_api.async_response
async def websocket_view(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Nastavení je dostupné správci HA.")
        return
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    runtime = getattr(entry, "runtime_data", None)
    if entry is None or entry.domain != DOMAIN or runtime is None or entry.state.value != "loaded":
        connection.send_error(msg["id"], "not_found", "Integrace routeru není načtená.")
        return
    try:
        await runtime.clients.async_set_view(connection.user.id, msg["view"])
    except Exception:
        connection.send_error(msg["id"], "save_failed", "Nastavení se nepodařilo uložit.")
        return
    connection.send_result(msg["id"], {"saved": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/wol",
        vol.Required("entry_id"): str,
        vol.Required("mac"): str,
    }
)
@websocket_api.async_response
async def websocket_wol(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "WOL je dostupné správci HA.")
        return
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    runtime = getattr(entry, "runtime_data", None)
    if entry is None or entry.domain != DOMAIN or runtime is None or entry.state.value != "loaded":
        connection.send_error(msg["id"], "not_found", "Integrace není načtená.")
        return
    mac = normalize_mac(msg["mac"])
    if mac is None or mac not in runtime.clients.inventory.known:
        connection.send_error(msg["id"], "not_found", "Klient není známý této integraci.")
        return
    try:
        await hass.async_add_executor_job(send_wol, mac)
    except OSError:
        connection.send_error(msg["id"], "send_failed", "WOL paket se nepodařilo odeslat.")
        return
    connection.send_result(msg["id"], {"sent": True})
