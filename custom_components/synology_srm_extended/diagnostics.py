"""Diagnostika sestavená explicitně bez config entry data a syrových odpovědí."""

import math

from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_OPTIONS, DOMAIN
from .srm.models import normalize_mac
from .srm.privacy import catalog_summary


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = entry.runtime_data
    registry = er.async_get(hass)
    trackers = [
        entity
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.platform == DOMAIN and entity.entity_id.startswith("device_tracker.")
    ]
    return {
        "integration_version": "0.1.12",
        "target": "RT6600ax / SRM 1.3.2-9366 Update 2",
        "read_only": False,
        "manual_actions": ["wol_from_ha_local_broadcast"],
        "options": {
            key: entry.options.get(key, default)
            for key, default in DEFAULT_OPTIONS.items()
            if key not in ("tracker_clients", "client_entities")
        },
        "selected_tracker_count": len(entry.options.get("tracker_clients", [])),
        "selected_client_count": len(entry.options.get("client_entities", [])),
        "tracker_registry": {
            "registered": len(trackers),
            "disabled": sum(entity.disabled_by is not None for entity in trackers),
            "with_state": sum(hass.states.get(entity.entity_id) is not None for entity in trackers),
        },
        "api_catalog": catalog_summary(runtime.api.catalog),
        "capabilities": dict(runtime.api.capabilities),
        "clients_available": runtime.clients.last_update_success,
        "client_read_duration_ms": runtime.clients.read_duration_ms,
        "client_rate_coverage": {
            kind: {
                "online": sum(
                    c.online is True and c.wireless is wireless
                    for c in runtime.clients.inventory.current.values()
                ),
                "with_rx_tx": sum(
                    c.online is True
                    and c.wireless is wireless
                    and all(key in c.attributes for key in ("transferRXRate", "transferTXRate"))
                    for c in runtime.clients.inventory.current.values()
                ),
            }
            for kind, wireless in (("wifi", True), ("ethernet", False))
        },
        "client_counts": dict(runtime.clients.summary),
        "traffic_client_matching": traffic_matching(
            (runtime.readings.data or {}).get("traffic"), runtime.clients.inventory.current
        ),
        "client_response_shape": runtime.clients.shape,
        "optional_api_status": dict(runtime.readings.statuses),
        "response_shapes": dict(runtime.readings.shapes),
        "diagnostics_format": 2,
        "read_duration_ms": dict(runtime.readings.durations),
        "recent_optional_samples": list(runtime.readings.samples),
        "router_metrics_units_verified": True,
        "router_metrics_evidence": (
            "RT6600ax SRM screenshots and utilization fields; memory KiB to MiB"
        ),
        "client_traffic_conversion": {
            "source_unit": entry.options.get("traffic_source_unit", "unknown"),
            "rx_direction": entry.options.get("traffic_rx_direction", "unknown"),
            "verification": "user_configured",
        },
    }


def traffic_matching(records, clients):
    """Páruje identitu pouze přes přesnou MAC; exportuje počty a anonymní vzorky."""
    if not isinstance(records, list):
        return {"available": False}
    matched = []
    for record in records:
        if not isinstance(record, dict):
            continue
        mac = normalize_mac(record.get("deviceID"))
        client = clients.get(mac) if mac else None
        if client is None:
            continue
        sample = {"connection": "wifi" if client.wireless else "ethernet", "online": client.online}
        for key in ("download", "upload"):
            value = record.get(key)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                sample[key] = value
        matched.append(sample)
    return {
        "available": True,
        "records": len(records),
        "matched_by_mac": len(matched),
        "unmatched": len(records) - len(matched),
        "examples": matched[:10],
        "units": "not_verified",
        "note": "Optional API sample; not synchronized with clients",
    }
