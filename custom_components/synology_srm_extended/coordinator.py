"""Klientský monitoring a nezávislé čtení volitelných odpovědí."""

import asyncio
import logging
from collections import deque
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STORAGE_VERSION
from .resources import snapshot
from .srm.client import SrmClient
from .srm.errors import AuthenticationError, SrmError
from .srm.models import Client, Inventory, clean_view, parse_clients, summarize
from .srm.privacy import response_shape

_LOGGER = logging.getLogger(__name__)


class ClientsCoordinator(DataUpdateCoordinator[dict[str, Client]]):
    def __init__(self, hass: HomeAssistant, entry, client: SrmClient, options: dict) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="SRM klienti",
            update_interval=timedelta(seconds=options["poll_interval"]),
        )
        self.client = client
        self.options = options
        self.inventory = Inventory()
        self._visibility_lock = asyncio.Lock()
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.clients")
        self.summary: dict[str, int | None] = {}
        self.shape: Any = None
        self.read_duration_ms: float | None = None

    async def async_load(self) -> None:
        self.inventory.restore(await self.store.async_load())
        # Starý automatický seznam není souhlasem s novým výběrovým režimem.
        self.inventory.monitored = set(self.options["client_entities"])

    async def _async_update_data(self) -> dict[str, Client]:
        started = perf_counter()
        try:
            response = await self.client.read("clients")
            self.shape = response_shape(response)
            clients = parse_clients(response)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Je nutné obnovit přihlášení SRM") from err
        except SrmError as err:
            raise UpdateFailed(str(err)) from None
        finally:
            self.read_duration_ms = round((perf_counter() - started) * 1000, 1)
        changed = self.inventory.update(
            clients,
            create=self.options["create_clients"],
            selected=set(self.options["client_entities"]),
        )
        self.summary = summarize(clients)
        if changed:
            self.store.async_delay_save(self.inventory.serialize, 5)
        return clients

    async def async_save(self) -> None:
        await self.store.async_save(self.inventory.serialize())

    async def async_set_hidden(self, mac: str, hidden: bool) -> None:
        async with self._visibility_lock:
            previous = set(self.inventory.hidden)
            if hidden:
                self.inventory.hidden.add(mac)
            else:
                self.inventory.hidden.discard(mac)
            try:
                await self.async_save()
            except Exception:
                self.inventory.hidden = previous
                raise

    async def async_set_view(self, user_id: str, view: dict) -> None:
        async with self._visibility_lock:
            previous = dict(self.inventory.views)
            self.inventory.views[user_id] = clean_view(view)
            try:
                await self.async_save()
            except Exception:
                self.inventory.views = previous
                raise


class ReadingsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Neznámé jednotky se nikdy nepřevádějí na domnělé senzory."""

    def __init__(self, hass, entry, client, options) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="SRM stav a diagnostika",
            update_interval=timedelta(minutes=5),
        )
        self.client = client
        self.options = options
        self.shapes: dict[str, Any] = {}
        self.statuses: dict[str, str] = {}
        self._skip: dict[str, str] = {}
        self.samples = deque(maxlen=3)
        self.history = deque(maxlen=288)
        self.durations: dict[str, float] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        from .srm.errors import PermissionDenied, TransportError, UnsupportedError

        keys = ["connection", "utilization", "system_info", "ethernet"]
        result = {}
        self.shapes = {}
        self.statuses = dict(self._skip)
        self.durations = {}
        for key in keys:
            if key in self._skip:
                continue
            started = perf_counter()
            try:
                raw = await self.client.read(key)
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed("Je nutné obnovit přihlášení SRM") from err
            except (UnsupportedError, PermissionDenied) as err:
                self.statuses[key] = f"{type(err).__name__}:{err.code}"
                self._skip[key] = self.statuses[key]
                self.shapes.pop(key, None)
            except TransportError:
                # Při výpadku nečekat postupně na timeout dvaceti volitelných API.
                self.statuses[key] = "transport_error"
                break
            except SrmError:
                self.statuses[key] = "response_error"
                self.shapes.pop(key, None)
            else:
                self.statuses[key] = "read_ok"
                if key in ("connection", "utilization", "system_info", "traffic", "ethernet"):
                    result[key] = raw
                self.shapes[key] = response_shape(raw)
            finally:
                self.durations[key] = round((perf_counter() - started) * 1000, 1)
        self.samples.append(
            {
                "sampled_at": datetime.now(UTC).isoformat(),
                "shapes": dict(self.shapes),
                "statuses": dict(self.statuses),
                "duration_ms": dict(self.durations),
            }
        )
        # Chyba jedné funkce nesmí zachovat její starou hodnotu jako aktuální.
        now = datetime.now(UTC).timestamp()
        while self.history and self.history[0]["time"] < now - 86400:
            self.history.popleft()
        self.history.append(snapshot(result, now))
        return result
