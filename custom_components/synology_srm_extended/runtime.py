"""Sdílená data jedné konfigurační položky."""

from dataclasses import dataclass

import aiohttp
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import ClientsCoordinator, ReadingsCoordinator
from .srm.client import SrmClient
from .srm.connection import base_url
from .transport import AiohttpTransport


def create_client(hass, data) -> tuple[SrmClient, aiohttp.ClientSession]:
    session = async_create_clientsession(
        hass,
        verify_ssl=data["verify_ssl"],
        auto_cleanup=False,
        cookie_jar=aiohttp.DummyCookieJar(),
        trust_env=False,
    )
    url = base_url(data["host"], data["port"], data["https"])
    return SrmClient(
        AiohttpTransport(session, url, data["verify_ssl"]),
        data["username"],
        data["password"],
    ), session


@dataclass
class RuntimeData:
    api: SrmClient
    session: aiohttp.ClientSession
    clients: ClientsCoordinator
    readings: ReadingsCoordinator
    router_device_id: str
