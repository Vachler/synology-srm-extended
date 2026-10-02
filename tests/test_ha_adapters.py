"""Jednotkové testy adaptéru s minimálními doubles, nikoli test běžícího HA."""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def adapters(monkeypatch):
    modules = {}

    def module(name, **attrs):
        mod = ModuleType(name)
        mod.__dict__.update(attrs)
        modules[name] = mod
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    class ConfigEntryAuthFailed(Exception):
        pass

    class UpdateFailed(Exception):
        pass

    class Coordinator:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, *args, **kwargs):
            self.last_update_success = True
            self.data = None
            self.listeners = []

        def async_add_listener(self, listener):
            self.listeners.append(listener)
            return lambda: self.listeners.remove(listener)

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return self.coordinator.last_update_success

    class Store:
        def __init__(self, *args):
            self.saved = None

        async def async_load(self):
            return self.saved

        async def async_save(self, data):
            self.saved = data

        def async_delay_save(self, callback, delay):
            self.saved = callback()

    module("homeassistant")
    module("homeassistant.core", HomeAssistant=object, callback=lambda fn: fn)
    module("homeassistant.exceptions", ConfigEntryAuthFailed=ConfigEntryAuthFailed)
    module("homeassistant.helpers")
    module("homeassistant.helpers.storage", Store=Store)
    module("homeassistant.helpers.device_registry", CONNECTION_NETWORK_MAC="mac", DeviceInfo=dict)
    module(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=Coordinator,
        CoordinatorEntity=CoordinatorEntity,
        UpdateFailed=UpdateFailed,
    )
    module("homeassistant.components")
    module(
        "homeassistant.components.binary_sensor",
        BinarySensorEntity=type("Binary", (), {}),
        BinarySensorDeviceClass=SimpleNamespace(CONNECTIVITY="connectivity"),
    )
    module(
        "homeassistant.components.device_tracker",
        SourceType=SimpleNamespace(ROUTER="router"),
    )
    module(
        "homeassistant.components.sensor",
        SensorEntity=type("Sensor", (), {}),
        SensorStateClass=SimpleNamespace(MEASUREMENT="measurement"),
    )
    module(
        "homeassistant.components.device_tracker.entity",
        BaseScannerEntity=type("BaseScanner", (), {}),
    )
    module("homeassistant.helpers.entity_registry")
    names = [
        "coordinator",
        "entity",
        "binary_sensor",
        "device_tracker",
        "sensor",
        "diagnostics",
        "registry",
    ]
    loaded = {name: importlib.import_module(f"component_under_test.{name}") for name in names}
    yield SimpleNamespace(**loaded, UpdateFailed=UpdateFailed)
    for name in names:
        sys.modules.pop(f"component_under_test.{name}", None)


def entry():
    from component_under_test.const import DEFAULT_OPTIONS

    return SimpleNamespace(
        entry_id="stable-entry",
        options=dict(DEFAULT_OPTIONS),
        async_on_unload=lambda fn: None,
    )


def response(online=True):
    return {"devices": [{"mac": "02:11:22:33:44:55", "hostname": "Telefon", "is_online": online}]}


async def setup_coordinator(adapters):
    config = entry()
    config.options["client_entities"] = ["02:11:22:33:44:55"]
    api = SimpleNamespace(read=AsyncMock(return_value=response()))
    coordinator = adapters.coordinator.ClientsCoordinator(None, config, api, config.options)
    coordinator.data = await coordinator._async_update_data()
    config.runtime_data = SimpleNamespace(clients=coordinator, router_device_id="router-id")
    return config, api, coordinator


async def test_unavailable_is_not_not_home_and_ids_survive_ip_changes(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    entity = adapters.device_tracker.ClientTracker(coordinator, config, "02:11:22:33:44:55")
    identity = entity._attr_unique_id
    assert entity.is_connected is True
    assert entity.available is True
    coordinator.last_update_success = False
    assert entity.available is False
    coordinator.last_update_success = True
    api.read.return_value = response(False)
    await coordinator._async_update_data()
    assert entity.available is True
    assert entity.is_connected is False
    api.read.return_value = {"devices": []}
    await coordinator._async_update_data()
    assert entity.available is False
    assert entity._attr_unique_id == identity
    assert coordinator.inventory.monitored == {"02:11:22:33:44:55"}


async def test_malformed_update_does_not_replace_last_inventory(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    api.read.return_value = {"unexpected": []}
    with pytest.raises(adapters.UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.inventory.current["02:11:22:33:44:55"].online is True


async def test_trackers_off_by_default_and_selection_deduplicated(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    entities = []
    await adapters.device_tracker.async_setup_entry(None, config, entities.extend)
    assert entities == []
    coordinator.options["create_trackers"] = True
    coordinator.options["tracker_clients"] = ["02:11:22:33:44:55"] * 2 + ["unknown"]
    await adapters.device_tracker.async_setup_entry(None, config, entities.extend)
    assert len(entities) == 1


async def test_dynamic_clients_added_once_and_kept_offline(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    entities = []
    await adapters.binary_sensor.async_setup_entry(None, config, entities.extend)
    for listener in coordinator.listeners:
        listener()
        listener()
    assert len(entities) == 1
    api.read.return_value = response(False)
    await coordinator._async_update_data()
    assert entities[0].is_on is False
    assert entities[0].device_info == {
        "identifiers": {("synology_srm_extended", "stable-entry_clients")}
    }


async def test_no_client_entities_by_default_but_list_is_visible_on_router(adapters):
    config = entry()
    api = SimpleNamespace(read=AsyncMock(return_value=response()))
    coordinator = adapters.coordinator.ClientsCoordinator(None, config, api, config.options)
    coordinator.data = await coordinator._async_update_data()
    config.runtime_data = SimpleNamespace(clients=coordinator, router_device_id="router-id")
    entities = []
    await adapters.binary_sensor.async_setup_entry(None, config, entities.extend)
    assert entities == []
    sensor = adapters.sensor.ClientCount(coordinator, config, "known")
    assert sensor.native_value == 1
    assert "clients" not in sensor.extra_state_attributes
    assert (
        sensor.extra_state_attributes["custom_ui_state_card"] == "synology-srm-clients-info-v0112"
    )
    assert sensor.extra_state_attributes["srm_entry_id"] == "stable-entry"
    assert sensor._attr_device_info == {"identifiers": {("synology_srm_extended", "stable-entry")}}


async def test_old_inventory_does_not_reenable_all_clients(adapters):
    config = entry()
    coordinator = adapters.coordinator.ClientsCoordinator(None, config, None, config.options)
    coordinator.store.saved = {
        "known": {"02:11:22:33:44:55": "Telefon"},
        "monitored": ["02:11:22:33:44:55"],
    }
    await coordinator.async_load()
    assert coordinator.inventory.known
    assert not coordinator.inventory.monitored


@pytest.mark.parametrize("cleanup", [False, True])
def test_registry_migration_moves_clients_and_only_removes_owned_unselected(adapters, cleanup):
    domain = "synology_srm_extended"
    config = entry()
    config.options["remove_unselected"] = cleanup
    config.options["client_entities"] = ["02:11:22:33:44:55"]
    config.options["create_trackers"] = True
    config.options["tracker_clients"] = ["02:11:22:33:44:55"]
    entities = {
        "device_tracker.legacy": SimpleNamespace(
            entity_id="device_tracker.legacy",
            platform=domain,
            config_entry_id="stable-entry",
            unique_id="02:11:22:33:44:55",
            device_id="old-selected",
        ),
        "binary_sensor.selected": SimpleNamespace(
            entity_id="binary_sensor.selected",
            platform=domain,
            config_entry_id="stable-entry",
            unique_id="stable-entry_02:11:22:33:44:55_connected",
            device_id="old-selected",
        ),
        "binary_sensor.unselected": SimpleNamespace(
            entity_id="binary_sensor.unselected",
            platform=domain,
            config_entry_id="stable-entry",
            unique_id="stable-entry_02:11:22:33:44:56_connected",
            device_id="old-unselected",
        ),
        "sensor.router": SimpleNamespace(
            entity_id="sensor.router",
            platform=domain,
            config_entry_id="stable-entry",
            unique_id="stable-entry_clients_online",
            device_id="router",
        ),
        "binary_sensor.foreign": SimpleNamespace(
            entity_id="binary_sensor.foreign",
            platform="other",
            config_entry_id="other-entry",
            unique_id="stable-entry_02:11:22:33:44:55_connected",
            device_id="foreign-device",
        ),
    }
    devices = {
        "router": SimpleNamespace(
            id="router",
            config_entry_id="stable-entry",
            identifiers={(domain, "stable-entry")},
        ),
        "old-selected": SimpleNamespace(
            id="old-selected",
            config_entry_id="stable-entry",
            identifiers={(domain, "stable-entry_02:11:22:33:44:55")},
        ),
        "old-unselected": SimpleNamespace(
            id="old-unselected",
            config_entry_id="stable-entry",
            identifiers={(domain, "stable-entry_02:11:22:33:44:56")},
        ),
        "foreign-device": SimpleNamespace(
            id="foreign-device",
            config_entry_id="other-entry",
            identifiers={("other", "mac")},
        ),
    }
    er = sys.modules["homeassistant.helpers.entity_registry"]
    dr = sys.modules["homeassistant.helpers.device_registry"]

    def update(entity_id, **changes):
        for key, value in changes.items():
            setattr(entities[entity_id], "unique_id" if key == "new_unique_id" else key, value)

    er.async_get = lambda hass: SimpleNamespace(
        async_remove=lambda entity_id: entities.pop(entity_id),
        async_update_entity=update,
        async_get_entity_id=lambda *args: None,
    )
    er.async_entries_for_config_entry = lambda reg, eid: [
        e for e in entities.values() if e.config_entry_id == eid
    ]
    er.async_entries_for_device = lambda reg, did, **kwargs: [
        e for e in entities.values() if e.device_id == did
    ]
    dr.async_get = lambda hass: SimpleNamespace(async_remove_device=lambda did: devices.pop(did))
    dr.async_entries_for_config_entry = lambda reg, eid: [
        d for d in devices.values() if d.config_entry_id == eid
    ]
    adapters.registry.migrate_client_entities(None, config, "router", config.options)
    assert entities["device_tracker.legacy"].device_id == "router"
    assert entities["device_tracker.legacy"].unique_id == "stable-entry_02:11:22:33:44:55_presence"
    assert entities["binary_sensor.selected"].device_id == "router"
    assert entities["binary_sensor.foreign"].device_id == "foreign-device"
    assert ("binary_sensor.unselected" in entities) is not cleanup
    if not cleanup:
        assert entities["binary_sensor.unselected"].device_id == "router"
    assert set(devices) == {"router", "foreign-device"}
    assert "sensor.router" in entities


async def test_optional_failure_does_not_break_other_reads(adapters):
    from component_under_test.srm.errors import UnsupportedError

    config = entry()
    config.options["collect_diagnostics"] = True

    async def read(key):
        if key == "utilization":
            raise UnsupportedError(102)
        return {"ipv4": {"conn_status": "normal"}}

    api = SimpleNamespace(read=AsyncMock(side_effect=read))
    coordinator = adapters.coordinator.ReadingsCoordinator(None, config, api, config.options)
    result = await coordinator._async_update_data()
    assert result["connection"]["ipv4"]["conn_status"] == "normal"
    api.read.reset_mock()
    await coordinator._async_update_data()
    assert "utilization" not in [call.args[0] for call in api.read.call_args_list]


async def test_wan_failure_does_not_publish_stale_state(adapters):
    from component_under_test.srm.errors import TransportError

    config = entry()
    api = SimpleNamespace(read=AsyncMock(return_value={"ipv4": {"conn_status": "normal"}}))
    coordinator = adapters.coordinator.ReadingsCoordinator(None, config, api, config.options)
    coordinator.data = await coordinator._async_update_data()
    entity = adapters.sensor.WanStatus(coordinator, config, "ipv4")
    assert entity.available
    api.read.side_effect = TransportError("Offline")
    coordinator.data = await coordinator._async_update_data()
    assert not entity.available
    assert entity.native_value is None


async def test_selected_tracker_created_even_when_missing_from_current_inventory(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    coordinator.options["create_trackers"] = True
    coordinator.options["tracker_clients"] = ["02:11:22:33:44:99"]
    entities = []
    await adapters.device_tracker.async_setup_entry(None, config, entities.extend)
    assert len(entities) == 1
    assert not entities[0].available
    assert entities[0]._attr_entity_category is None
    assert entities[0]._attr_entity_registry_enabled_default


async def test_hidden_clients_persist_and_do_not_change_trackers(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    mac = "02:11:22:33:44:55"
    await coordinator.async_set_hidden(mac, True)
    assert coordinator.store.saved["hidden"] == [mac]
    await coordinator._async_update_data()
    assert mac in coordinator.inventory.hidden
    assert mac in coordinator.inventory.current
    assert mac in coordinator.inventory.monitored
    await coordinator.async_set_hidden(mac, False)
    assert coordinator.store.saved["hidden"] == []


async def test_failed_visibility_save_rolls_back(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    coordinator.store.async_save = AsyncMock(side_effect=OSError("disk"))
    with pytest.raises(OSError):
        await coordinator.async_set_hidden("02:11:22:33:44:55", True)
    assert not coordinator.inventory.hidden


async def test_router_metrics_independent_of_client_tracking_and_failures(adapters):
    from component_under_test.srm.errors import ResponseError

    config = entry()

    async def read(key):
        return {
            "utilization": {
                "cpu": {"user_load": 7, "system_load": 5, "other_load": 2},
                "memory": {"real_usage": 59, "swap_usage": 13},
                "network": [{"device": "eth0"}, {"device": "total"}],
            },
            "system_info": {"nodes": [{}, {}]},
            "ethernet": {"nodes": []},
            "connection": {},
        }[key]

    api = SimpleNamespace(read=AsyncMock(side_effect=read))
    coordinator = adapters.coordinator.ReadingsCoordinator(None, config, api, config.options)
    coordinator.data = await coordinator._async_update_data()
    sensor = adapters.sensor.RouterMetric(coordinator, config, "ram_usage")
    assert sensor.native_value == 59
    assert sensor.available
    assert adapters.sensor.RouterMetric(coordinator, config, "mesh_nodes").native_value == 2
    assert adapters.sensor.RouterMetric(coordinator, config, "network_interfaces").native_value == 1
    assert len(coordinator.samples) == 1
    api.read.side_effect = ResponseError("test")
    coordinator.data = await coordinator._async_update_data()
    assert not sensor.available
    assert sensor.native_value is None


async def test_diagnostics_history_is_bounded_and_sanitized(adapters):
    config = entry()
    config.options["collect_diagnostics"] = True
    api = SimpleNamespace(read=AsyncMock(return_value={"hostname": "SECRET", "uptime": 123}))
    coordinator = adapters.coordinator.ReadingsCoordinator(None, config, api, config.options)
    for _ in range(5):
        await coordinator._async_update_data()
    assert len(coordinator.samples) == 3
    assert "SECRET" not in str(coordinator.samples)
    assert coordinator.samples[-1]["sampled_at"]
    assert coordinator.durations["utilization"] >= 0


async def test_server_view_survives_reload_and_failed_save(adapters):
    config, api, coordinator = await setup_coordinator(adapters)
    view = {"sort": "signal", "filter": "online", "visibility": "visible", "descending": True}
    await coordinator.async_set_view("user-one", view)
    stored = coordinator.store.saved
    from component_under_test.srm.models import Inventory

    restored = Inventory()
    restored.restore(stored)
    assert restored.views["user-one"] == view
    assert "user-two" not in restored.views
    coordinator.store.async_save = AsyncMock(side_effect=OSError("disk"))
    with pytest.raises(OSError):
        await coordinator.async_set_view("user-one", {"sort": "name"})
    assert coordinator.inventory.views["user-one"] == view


def test_memory_ratio_and_invalid_data(adapters):
    config = entry()
    coordinator = SimpleNamespace(
        data={
            "utilization": {
                "memory": {
                    "total_real": 1000,
                    "avail_real": 100,
                    "buffer": 100,
                    "cached": 200,
                }
            }
        },
        last_update_success=True,
    )
    sensor = adapters.sensor.RouterMetric(coordinator, config, "ram_calculated")
    assert sensor.native_value == 60
    assert sensor._attr_native_unit_of_measurement == "%"
    coordinator.data["utilization"]["memory"]["total_real"] = 0
    assert sensor.native_value is None
    coordinator.data["utilization"]["memory"]["total_real"] = 100
    assert sensor.native_value is None


def test_cpu_percentage_and_memory_units(adapters):
    coordinator = SimpleNamespace(
        data={
            "utilization": {
                "cpu": {"user_load": 7, "system_load": 5, "other_load": 3},
                "memory": {
                    "memory_size": 1048576,
                    "total_real": 824612,
                    "avail_real": 88236,
                    "cached": 180716,
                    "buffer": 28868,
                },
            }
        },
        last_update_success=True,
    )
    cpu = adapters.sensor.RouterMetric(coordinator, entry(), "cpu_total")
    assert cpu.native_value == 15
    assert cpu._attr_native_unit_of_measurement == "%"
    ram = adapters.sensor.RouterMetric(coordinator, entry(), "ram_usage")
    assert ram.resource_details["Celkem (MiB)"] == 1024
    assert ram.resource_details["Rezervováno (MiB)"] == 218.7
    coordinator.data["utilization"]["cpu"]["other_load"] = 99
    assert cpu.native_value is None


def test_client_uses_more_info_hook(adapters):
    coordinator = SimpleNamespace(inventory=SimpleNamespace(known={}))
    sensor = adapters.binary_sensor.ClientConnected(coordinator, entry(), "02:11:22:33:44:55")
    assert sensor.detail_attributes["custom_ui_state_card"] == "synology-srm-client-info-v0112"
    assert "custom_ui_more_info" not in sensor.detail_attributes


def test_all_client_counts_have_scoped_details(adapters):
    coordinator = SimpleNamespace(inventory=SimpleNamespace(current={}))
    for key in ("online", "offline", "wifi", "lan", "guest", "known"):
        sensor = adapters.sensor.ClientCount(coordinator, entry(), key)
        assert sensor.extra_state_attributes["srm_client_scope"] == key


def test_count_attributes_independent_of_inventory_size(adapters):
    import json

    inventory = SimpleNamespace(current={})
    coordinator = SimpleNamespace(inventory=inventory, summary={"known": 0})
    for key in ("known", "online", "offline", "wifi", "lan", "guest"):
        entity = adapters.sensor.ClientCount(coordinator, entry(), key)
        before = dict(entity.extra_state_attributes)
        inventory.current = {
            str(i): SimpleNamespace(attributes={"hostname": "x" * 1000}) for i in range(1000)
        }
        assert entity.extra_state_attributes == before
        assert len(json.dumps(before).encode()) < 512
        assert "clients" not in before
        inventory.current = {}
