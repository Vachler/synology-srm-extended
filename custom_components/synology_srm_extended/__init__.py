"""Synology SRM Extended: čtecí integrace pro RT6600ax."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_OPTIONS, DOMAIN, STORAGE_VERSION
from .coordinator import ClientsCoordinator, ReadingsCoordinator
from .localization import device_labels
from .panel import async_register_panel, async_setup_panel, panel_path
from .registry import migrate_client_entities
from .runtime import RuntimeData, create_client
from .srm.errors import SrmError

type SrmConfigEntry = ConfigEntry[RuntimeData]


def platforms(entry: SrmConfigEntry) -> list[Platform]:
    result = [Platform.SENSOR, Platform.BINARY_SENSOR]
    if entry.options.get("create_trackers", False):
        result.append(Platform.DEVICE_TRACKER)
    return result


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await async_setup_panel(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SrmConfigEntry) -> bool:
    options = {**DEFAULT_OPTIONS, **entry.options}
    api, session = create_client(hass, entry.data)
    clients = ClientsCoordinator(hass, entry, api, options)
    readings = ReadingsCoordinator(hass, entry, api, options)
    try:
        await clients.async_load()
        # Dostupnost klientů nesmí záviset na volitelném katalogu.
        await clients.async_config_entry_first_refresh()
        try:
            await api.discover()
        except SrmError:
            pass
        await readings.async_refresh()
        registry = dr.async_get(hass)
        router = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Synology",
            model="RT6600ax",
            name="Synology RT6600ax",
            configuration_url=f"homeassistant://{panel_path(entry.entry_id)}",
        )
        entry.runtime_data = RuntimeData(api, session, clients, readings, router.id)
        client_target = router.id
        if (options["create_clients"] and options["client_entities"]) or (
            options["create_trackers"] and options["tracker_clients"]
        ):
            group_name, group_model = await hass.async_add_executor_job(
                device_labels, hass.config.language
            )
            client_group = registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, f"{entry.entry_id}_clients")},
                name=group_name,
                manufacturer="Synology",
                model=group_model,
            )
            client_target = client_group.id
        migrate_client_entities(hass, entry, client_target, options)
        await hass.config_entries.async_forward_entry_setups(entry, platforms(entry))
        await async_register_panel(hass, entry)
    except BaseException:
        # Také zrušený setup nesmí ponechat session nebo pollovací callbacky.
        await clients.async_shutdown()
        await readings.async_shutdown()
        session.detach()
        raise
    entry.async_on_unload(session.detach)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SrmConfigEntry) -> bool:
    # Platformy mohou pocházet ze starých options před automatickým reloadem.
    loaded = [Platform.SENSOR, Platform.BINARY_SENSOR]
    if entry.runtime_data.clients.options["create_trackers"]:
        loaded.append(Platform.DEVICE_TRACKER)
    if not await hass.config_entries.async_unload_platforms(entry, loaded):
        return False
    runtime = entry.runtime_data
    await runtime.clients.async_shutdown()
    await runtime.readings.async_shutdown()
    try:
        await runtime.clients.async_save()
        await runtime.api.logout()
    finally:
        runtime.session.detach()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: SrmConfigEntry) -> None:
    from homeassistant.helpers.storage import Store

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.clients").async_remove()
