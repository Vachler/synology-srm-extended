"""POST transport, obnova relace a striktně omezený čtecí povrch."""

import asyncio
import re
from typing import Any, Protocol

from .errors import (
    ApiError,
    AuthenticationError,
    PermissionDenied,
    ResponseError,
    TwoFactorRequired,
    UnsupportedError,
)
from .specs import READ_BY_KEY


class Transport(Protocol):
    async def post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        """Odeslat formulář na stejný router, bez přesměrování a bez logování dat."""


class SrmClient:
    """Jedna izolovaná relace, maximálně jeden síťový požadavek současně."""

    def __init__(self, transport: Transport, username: str, password: str) -> None:
        self._transport = transport
        self._username = username
        self._password = password
        self._sid: str | None = None
        self._token: str | None = None
        self._lock = asyncio.Lock()
        self.catalog: dict[str, dict[str, Any]] = {}
        self.capabilities: dict[str, str] = {}

    @staticmethod
    def _unwrap(body: dict[str, Any], *, login: bool = False) -> Any:
        if not isinstance(body, dict) or type(body.get("success")) is not bool:
            raise ResponseError("Neplatná obálka SRM")
        if body["success"]:
            if "data" not in body:
                raise ResponseError("Chybí data SRM")
            return body["data"]
        error = body.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        if type(code) is not int:
            raise ResponseError("Neplatný kód chyby SRM")
        if login:
            if code in (403, 404):
                raise TwoFactorRequired(code)
            raise AuthenticationError(code)
        if code in (102, 103, 104):
            raise UnsupportedError(code)
        if code in (105, 117):
            raise PermissionDenied(code)
        raise ApiError(code)

    async def _login(self) -> None:
        self._sid = None
        self._token = None
        data = self._unwrap(
            await self._transport.post(
                "auth.cgi",
                {
                    "api": "SYNO.API.Auth",
                    "version": "2",
                    "method": "Login",
                    "account": self._username,
                    "passwd": self._password,
                    "format": "sid",
                },
            ),
            login=True,
        )
        if not isinstance(data, dict) or not isinstance(data.get("sid"), str) or not data["sid"]:
            raise ResponseError("Přihlášení nevrátilo relaci")
        self._sid = data["sid"]
        if isinstance(data.get("synotoken"), str):
            self._token = data["synotoken"]

    async def _authenticated(self, path: str, params: dict[str, str]) -> Any:
        async with self._lock:
            for attempt in range(2):
                if self._sid is None:
                    await self._login()
                payload = {**params, "_sid": self._sid}
                if self._token:
                    payload["SynoToken"] = self._token
                try:
                    return self._unwrap(await self._transport.post(path, payload))
                except ApiError as err:
                    if err.code not in (106, 107):
                        raise
                    self._sid = None
                    self._token = None
                    if attempt:
                        raise AuthenticationError(err.code) from None
        raise AuthenticationError(106)

    async def discover(self) -> None:
        """Katalog není podmínkou funkčnosti již známého klientského API."""
        data = await self._authenticated(
            "query.cgi",
            {
                "api": "SYNO.API.Info",
                "version": "1",
                "method": "query",
                "query": "ALL",
            },
        )
        if not isinstance(data, dict):
            raise ResponseError("Neplatný katalog SRM")
        self.catalog = {
            name: meta
            for name, meta in data.items()
            if isinstance(name, str) and isinstance(meta, dict)
        }

    async def read(self, key: str) -> Any:
        """Volat lze pouze pevné čtecí specifikace; nelze dodat metodu ani parametry."""
        if key not in READ_BY_KEY:
            raise ValueError("Požadavek není na seznamu povolených čtení")
        spec = READ_BY_KEY[key]
        meta = self.catalog.get(spec.api, {})
        # Nevolíme automaticky nejvyšší ani nižší verzi: parser očekává přesný kontrakt.
        minimum, maximum = meta.get("minVersion"), meta.get("maxVersion")
        if (type(minimum) is int and spec.version < minimum) or (
            type(maximum) is int and spec.version > maximum
        ):
            self.capabilities[key] = "unsupported_version"
            raise UnsupportedError(104)
        path = meta.get("path", "entry.cgi")
        # Katalog nesmí změnit host, vnést query string či vyvést požadavek mimo /webapi/.
        if not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.cgi", path):
            self.capabilities[key] = "invalid_path"
            raise ResponseError("Nepodporovaná cesta API")
        params = {
            "api": spec.api,
            "version": str(spec.version),
            "method": spec.method,
            **dict(spec.params),
        }
        try:
            data = await self._authenticated(path, params)
        except UnsupportedError:
            self.capabilities[key] = "unsupported"
            raise
        except PermissionDenied:
            self.capabilities[key] = "permission_denied"
            raise
        except (ApiError, ResponseError):
            self.capabilities[key] = "error"
            raise
        self.capabilities[key] = "read_ok"
        return data

    async def logout(self) -> None:
        """Ukončit pouze vlastní relaci, bez propagace chyb při úklidu."""
        async with self._lock:
            sid, self._sid = self._sid, None
            self._token = None
            if sid:
                from .errors import SrmError

                try:
                    await self._transport.post(
                        "auth.cgi",
                        {
                            "api": "SYNO.API.Auth",
                            "version": "2",
                            "method": "Logout",
                            "_sid": sid,
                        },
                    )
                except SrmError:
                    pass
