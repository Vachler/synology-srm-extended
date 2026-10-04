"""Souhrny klientů a nezměněný stav WAN dodaný SRM."""

import math

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback

from .entity import RouterEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        ClientCount(entry.runtime_data.clients, entry, key)
        for key in ("known", "online", "offline", "wifi", "lan", "guest")
    )
    readings = entry.runtime_data.readings
    async_add_entities(RouterMetric(readings, entry, key) for key in ROUTER_METRICS)
    added = set()

    @callback
    def add_wan():
        connection = (readings.data or {}).get("connection", {})
        if not isinstance(connection, dict):
            return
        new = []
        for family in ("ipv4", "ipv6"):
            record = connection.get(family)
            if (
                family not in added
                and isinstance(record, dict)
                and isinstance(
                    record.get("conn_status"),
                    str,
                )
            ):
                added.add(family)
                new.append(WanStatus(readings, entry, family))
        if new:
            async_add_entities(new)

    add_wan()
    entry.async_on_unload(readings.async_add_listener(add_wan))


class ClientCount(RouterEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:devices"

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator, entry, f"clients_{key}")
        self.entry_id = entry.entry_id
        self.key = key
        self._attr_translation_key = f"clients_{key}"

    @property
    def native_value(self):
        return self.coordinator.summary.get(self.key)

    @property
    def extra_state_attributes(self):
        return {
            "custom_ui_state_card": "synology-srm-clients-info-v0113",
            "srm_entry_id": self.entry_id,
            "srm_client_scope": self.key,
        }


class WanStatus(RouterEntity, SensorEntity):
    _attr_icon = "mdi:wan"

    def __init__(self, coordinator, entry, family):
        super().__init__(coordinator, entry, f"wan_{family}")
        self.family = family
        self._attr_translation_key = f"wan_{family}"

    @property
    def record(self):
        connection = (self.coordinator.data or {}).get("connection", {})
        value = connection.get(self.family) if isinstance(connection, dict) else None
        return value if isinstance(value, dict) else {}

    @property
    def available(self):
        return super().available and isinstance(self.record.get("conn_status"), str)

    @property
    def native_value(self):
        value = self.record.get("conn_status")
        return value[:255] if isinstance(value, str) else None

    @property
    def extra_state_attributes(self):
        return {
            key: value
            for key in ("ip", "ifname", "pppoe")
            if type(value := self.record.get(key)) in (str, bool)
        }


ROUTER_METRICS = {
    "cpu_total": ("CPU – celkové využití", "utilization", "cpu", "calculated"),
    "cpu_user": ("CPU – uživatelské zatížení", "utilization", "cpu", "user_load"),
    "cpu_system": ("CPU – systémové zatížení", "utilization", "cpu", "system_load"),
    "cpu_other": ("CPU – ostatní zatížení", "utilization", "cpu", "other_load"),
    "ram_calculated": ("RAM – využití bez cache a bufferů", "utilization", "memory", "calculated"),
    "ram_usage": ("Využití RAM podle SRM", "utilization", "memory", "real_usage"),
    "swap_usage": ("Využití swapu podle SRM", "utilization", "memory", "swap_usage"),
    "mesh_nodes": ("Počet uzlů mesh", "system_info", "nodes", None),
    "network_interfaces": ("Počet síťových rozhraní", "utilization", "network", None),
}


class RouterMetric(RouterEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:router-network"

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator, entry, key)
        self.clients_coordinator = (
            entry.runtime_data.clients if hasattr(entry, "runtime_data") else None
        )
        self.key = key
        self._attr_translation_key = key
        self.entry_id = entry.entry_id
        if key.startswith("cpu_") or key in ("ram_calculated", "ram_usage", "swap_usage"):
            self._attr_native_unit_of_measurement = "%"
            self._attr_icon = "mdi:cpu-64-bit" if key.startswith("cpu_") else "mdi:memory"

    @property
    def native_value(self):
        _, source, group, field = ROUTER_METRICS[self.key]
        raw = (self.coordinator.data or {}).get(source)
        record = raw.get(group) if isinstance(raw, dict) else None
        if self.key == "cpu_total":
            if not isinstance(record, dict):
                return None
            parts = [record.get(k) for k in ("user_load", "system_load", "other_load")]
            if any(
                type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100
                for v in parts
            ):
                return None
            return sum(parts) if sum(parts) <= 100 else None
        if self.key == "ram_calculated":
            if not isinstance(record, dict):
                return None
            numbers = [record.get(k) for k in ("total_real", "avail_real", "buffer", "cached")]
            if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in numbers):
                return None
            total, free, buffers, cache = numbers
            if total <= 0 or free + buffers + cache > total:
                return None
            return round(100 * (total - free - buffers - cache) / total, 1)
        if field is None:
            if not isinstance(record, list):
                return None
            if self.key == "network_interfaces":
                names = [item.get("device") for item in record if isinstance(item, dict)]
                if len(names) != len(record) or any(
                    not isinstance(name, str) or not name for name in names
                ):
                    return None
                return len({name for name in names if name != "total"})
            return len(record)
        value = record.get(field) if isinstance(record, dict) else None
        # Uchováváme původní hodnotu, nepředpokládáme procenta ani měřítko.
        return (
            value
            if type(value) in (int, float) and math.isfinite(value) and value >= 0 and value <= 100
            else None
        )

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self):
        if self.key == "mesh_nodes":
            return {
                "custom_ui_state_card": "synology-srm-resource-info-v0113",
                "srm_entry_id": self.entry_id,
                "resource_kind": "mesh_nodes",
            }
        if ROUTER_METRICS[self.key][3] is None:
            return None
        notes = {
            "cpu_total": "Součet uživatelského, systémového a ostatního využití CPU v procentech.",
            "cpu_user": "Zatížení aplikacemi a uživatelskými procesy.",
            "cpu_system": "Zatížení jádrem a systémovými operacemi.",
            "cpu_other": "Ostatní kategorie zatížení hlášené routerem.",
            "ram_usage": (
                "Využití paměti v procentech hlášené SRM. Rezervovaná paměť není v základu procent."
            ),
            "swap_usage": "Využití odkládací paměti podle SRM.",
            "ram_calculated": (
                "100 × (total_real − avail_real − buffer − cached) / total_real. "
                "Cache a buffery se nepočítají jako obsazené aplikacemi. "
                "Výsledek se může lišit od zaokrouhlení SRM."
            ),
        }
        return {
            "custom_ui_state_card": "synology-srm-resource-info-v0113",
            "srm_entry_id": self.entry_id,
            "resource_kind": self.key,
            "measurement_note": notes.get(self.key, ""),
            "resource_details": self.resource_details,
            "refresh_note": (
                "Systémové údaje se načítají každých 5 minut; interval klientů je samostatný."
            ),
        }

    @property
    def resource_details(self):
        if not self.key.startswith("ram_"):
            return {}
        memory = (self.coordinator.data or {}).get("utilization", {}).get("memory", {})
        keys = ("memory_size", "total_real", "avail_real", "cached", "buffer")
        values = [memory.get(key) for key in keys]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            return {}
        installed, total, free, cache, buffers = values
        used = total - free - cache - buffers
        if installed < total or used < 0:
            return {}
        return {
            label: round(value / 1024, 1)
            for label, value in {
                "Celkem (MiB)": installed,
                "Využitá paměť (MiB)": used,
                "Volná paměť (MiB)": free,
                "Cache (MiB)": cache,
                "Buffery (MiB)": buffers,
                "Rezervováno (MiB)": installed - total,
            }.items()
        }
