"""Přesun starých klientských entit pod router se zachováním entity_id."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .srm.models import normalize_mac


def client_identity(unique_id: str, entry_id: str) -> tuple[str, str] | None:
    prefix = f"{entry_id}_"
    if not unique_id.startswith(prefix):
        return None
    value = unique_id[len(prefix) :]
    for kind in ("connected", "presence"):
        suffix = f"_{kind}"
        if value.endswith(suffix):
            mac = normalize_mac(value[: -len(suffix)])
            if mac and value == f"{mac}_{kind}":
                return mac, kind
    return None


def migrate_client_entities(hass, entry, router_id: str, options: dict) -> None:
    """Mění pouze vlastní klientské entity; router a jiné integrace nikdy nemaže."""
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    selected = set(options["client_entities"]) if options["create_clients"] else set()
    trackers = set(options["tracker_clients"]) if options["create_trackers"] else set()
    for entity in list(er.async_entries_for_config_entry(entities, entry.entry_id)):
        if entity.platform != DOMAIN:
            continue
        identity = client_identity(entity.unique_id, entry.entry_id)
        legacy_mac = normalize_mac(entity.unique_id)
        legacy_tracker = entity.entity_id.startswith("device_tracker.") and legacy_mac
        if identity is None and legacy_tracker:
            identity = (legacy_mac, "presence")
        if identity is None:
            continue
        mac, kind = identity
        keep = mac in (selected if kind == "connected" else trackers)
        if options["remove_unselected"] and not keep:
            entities.async_remove(entity.entity_id)
        else:
            updates = {"device_id": router_id}
            if legacy_tracker:
                target = f"{entry.entry_id}_{mac}_presence"
                if not entities.async_get_entity_id("device_tracker", DOMAIN, target):
                    updates["new_unique_id"] = target
            entities.async_update_entity(entity.entity_id, **updates)
    # Po přesunu je možné odstranit jen prázdné klientské obálky této integrace.
    for device in list(dr.async_entries_for_config_entry(devices, entry.entry_id)):
        if device.id == router_id or device.config_entry_id != entry.entry_id:
            continue
        owned_client = any(
            domain == DOMAIN and client_identity(f"{identifier}_connected", entry.entry_id)
            for domain, identifier in device.identifiers
        )
        if owned_client and not er.async_entries_for_device(
            entities, device.id, include_disabled_entities=True
        ):
            devices.async_remove_device(device.id)
