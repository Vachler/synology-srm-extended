"""Společné identity a metadata entit."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class RouterEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})


class ClientEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, mac, kind):
        super().__init__(coordinator)
        self.mac = mac
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{mac}_{kind}"
        self._attr_translation_placeholders = {
            "client": coordinator.inventory.known.get(mac, mac),
        }

    @property
    def client(self):
        return self.coordinator.inventory.current.get(self.mac)

    @property
    def available(self) -> bool:
        return super().available and self.client is not None and self.client.online is not None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_clients")},
        )

    @property
    def detail_attributes(self):
        return {
            "custom_ui_state_card": "synology-srm-client-info-v0113",
            "srm_entry_id": self.entry.entry_id,
            "srm_client_mac": self.mac,
        }
