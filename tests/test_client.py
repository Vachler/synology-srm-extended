"""Ověření obnovy session, seznamu čtení a sanitizovaných chyb."""

import asyncio
from collections import deque

import pytest
from srm.client import SrmClient
from srm.errors import (
    ApiError,
    AuthenticationError,
    PermissionDenied,
    ResponseError,
    TwoFactorRequired,
    UnsupportedError,
)
from srm.specs import READS


def ok(data):
    return {"success": True, "data": data}


def error(code):
    return {"success": False, "error": {"code": code, "message": "SECRET response"}}


class FakeTransport:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.requests = []
        self.active = 0
        self.max_active = 0

    async def post(self, path, data):
        self.requests.append((path, dict(data)))
        self.active += 1
        self.max_active = max(self.active, self.max_active)
        await asyncio.sleep(0)
        self.active -= 1
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


def client_for(*responses):
    transport = FakeTransport(responses)
    return SrmClient(transport, "USER_SECRET", "PASSWORD_SECRET"), transport


async def test_login_is_post_payload_and_session_is_reused():
    client, transport = client_for(ok({"sid": "SID_SECRET"}), ok({}), ok({}))
    await client.read("clients")
    await client.read("clients")
    assert len(transport.requests) == 3
    assert transport.requests[0][1]["passwd"] == "PASSWORD_SECRET"
    for path, _payload in transport.requests:
        assert "?" not in path
        assert "PASSWORD_SECRET" not in path
    assert "passwd" not in transport.requests[1][1]
    assert transport.requests[1][1]["_sid"] == "SID_SECRET"
    assert transport.requests[1][1]["version"] == "5"


async def test_expired_session_reauth_once():
    client, transport = client_for(
        ok({"sid": "old"}),
        error(106),
        ok({"sid": "new"}),
        ok({"devices": []}),
    )
    assert await client.read("clients") == {"devices": []}
    assert [p.get("_sid") for _, p in transport.requests] == [None, "old", None, "new"]


async def test_repeated_expiry_stops():
    client, transport = client_for(ok({"sid": "old"}), error(107), ok({"sid": "new"}), error(106))
    with pytest.raises(AuthenticationError):
        await client.read("clients")
    assert len(transport.requests) == 4


async def test_concurrent_reads_share_login_and_do_not_overlap():
    client, transport = client_for(ok({"sid": "sid"}), ok({}), ok({}))
    await asyncio.gather(client.read("clients"), client.read("connection"))
    assert transport.max_active == 1
    assert sum(data["method"] == "Login" for _, data in transport.requests) == 1


@pytest.mark.parametrize("key", ["reboot", "shutdown", "set", "SYNO.Core.System", "request"])
async def test_write_or_arbitrary_api_is_rejected_without_network(key):
    client, transport = client_for()
    with pytest.raises(ValueError):
        await client.read(key)
    assert not transport.requests


def test_all_polling_specs_are_reads():
    assert all(s.method in {"get", "list"} for s in READS)
    assert len({s.key for s in READS}) == len(READS)


@pytest.mark.parametrize(
    "path", ["https://evil.invalid", "../auth.cgi", "entry.cgi?sid=x", "/entry.cgi"]
)
async def test_catalog_cannot_redirect_credentials(path):
    client, transport = client_for()
    client.catalog = {"SYNO.Core.Network.NSM.Device": {"path": path}}
    with pytest.raises(ResponseError):
        await client.read("clients")
    assert not transport.requests


async def test_version_is_not_silently_downgraded():
    client, transport = client_for()
    client.catalog = {"SYNO.Core.Network.NSM.Device": {"minVersion": 1, "maxVersion": 4}}
    with pytest.raises(UnsupportedError):
        await client.read("clients")
    assert not transport.requests


@pytest.mark.parametrize("code,exception", [(400, AuthenticationError), (403, TwoFactorRequired)])
async def test_auth_errors_do_not_leak_body(code, exception):
    client, transport = client_for(error(code))
    with pytest.raises(exception) as caught:
        await client.read("clients")
    assert "SECRET" not in str(caught.value)
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "code,exception", [(105, PermissionDenied), (102, UnsupportedError), (999, ApiError)]
)
async def test_optional_error_does_not_break_next_read(code, exception):
    client, _ = client_for(ok({"sid": "sid"}), error(code), ok({"devices": []}))
    with pytest.raises(exception):
        await client.read("utilization")
    assert await client.read("clients") == {"devices": []}


@pytest.mark.parametrize("body", [{}, {"success": "false"}, {"success": True}, error("secret")])
def test_malformed_envelope(body):
    with pytest.raises(ResponseError):
        SrmClient._unwrap(body)
