"""Asynchronní HTTP transport pro Home Assistant."""

import json
from typing import Any

import aiohttp

from .srm.errors import CertificateError, ResponseError, TransportError

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class AiohttpTransport:
    def __init__(self, session: aiohttp.ClientSession, url: str, verify_ssl: bool) -> None:
        self._session = session
        self._url = url
        self._verify_ssl = verify_ssl

    async def post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            async with self._session.post(
                f"{self._url}/webapi/{path}",
                data=data,
                ssl=None if self._verify_ssl else False,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    raise TransportError(f"HTTP {response.status}")
                chunks = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise ResponseError("Odpověď překročila povolenou velikost")
                try:
                    body = json.loads(chunks)
                except (ValueError, UnicodeError):
                    raise ResponseError("Router nevrátil JSON") from None
                if not isinstance(body, dict):
                    raise ResponseError("Router nevrátil objekt JSON")
                return body
        except aiohttp.ClientConnectorCertificateError:
            raise CertificateError("Certifikát nelze ověřit") from None
        except (TimeoutError, aiohttp.ClientError, OSError):
            # Původní výjimka může obsahovat URL nebo data serveru.
            raise TransportError("Spojení s routerem selhalo") from None
