"""Klientské připojení; nedostupný router není odpojený klient."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import callback

from .entity import ClientEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data.clients
    if not coordinator.options["create_clients"]:
        return
    added = set()

    @callback
    def add_clients():
        new = coordinator.inventory.monitored - added
        added.update(new)
        async_add_entities(ClientConnected(coordinator, entry, mac) for mac in sorted(new))

    add_clients()
    entry.async_on_unload(coordinator.async_add_listener(add_clients))


class ClientConnected(ClientEntity, BinarySensorEntity):
    _attr_translation_key = "client_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, entry, mac):
        super().__init__(coordinator, entry, mac, "connected")

    @property
    def is_on(self):
        return self.client.online if self.client else None

    @property
    def extra_state_attributes(self):
        if not self.client:
            return {**self.detail_attributes, "mac": self.mac}
        return {
            **self.detail_attributes,
            "mac": self.mac,
            "is_wireless": self.client.wireless,
            **self.client.attributes,
        }
