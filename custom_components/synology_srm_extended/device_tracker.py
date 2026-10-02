"""Trackery se vytvářejí pouze při výslovném povolení a výběru klienta."""

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.entity import BaseScannerEntity

from .entity import ClientEntity
from .srm.models import normalize_mac

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data.clients
    if not coordinator.options["create_trackers"]:
        return
    selected = {
        mac
        for value in coordinator.options["tracker_clients"]
        if (mac := normalize_mac(value)) is not None
    }
    async_add_entities(ClientTracker(coordinator, entry, mac) for mac in sorted(selected))


class ClientTracker(ClientEntity, BaseScannerEntity):
    # ScannerEntity automaticky registruje samostatné zařízení podle MAC.
    # Zde je přítomnost klienta údajem hlavního zařízení routeru.
    _attr_translation_key = "presence"
    _attr_source_type = SourceType.ROUTER
    _attr_entity_category = None
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, entry, mac):
        super().__init__(coordinator, entry, mac, "presence")

    @property
    def is_connected(self):
        return self.client.online if self.client else None

    @property
    def mac_address(self):
        return self.mac

    @property
    def ip_address(self):
        return self.client.attributes.get("ip_addr") if self.client else None

    @property
    def hostname(self):
        return self.coordinator.inventory.known.get(self.mac)

    @property
    def extra_state_attributes(self):
        return {
            **self.detail_attributes,
            "mac": self.mac,
            "ip": self.ip_address,
            "hostname": self.hostname,
        }
