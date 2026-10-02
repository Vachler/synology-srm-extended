"""Skutečné HTTP požadavky proti lokálnímu serveru, bez routeru."""

import json

import aiohttp
import pytest
from aiohttp import web
from component_under_test.srm.client import SrmClient
from component_under_test.srm.errors import ResponseError, TransportError
from component_under_test.transport import AiohttpTransport


@pytest.fixture
async def server():
    runners = []

    async def start(handler):
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", handler)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        runners.append(runner)
        return f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"

    yield start
    for runner in runners:
        await runner.cleanup()


async def test_real_post_login_and_client_read(server):
    calls = []

    async def handler(request):
        payload = dict(await request.post())
        calls.append((request.method, request.path, request.query_string, payload))
        data = {"sid": "SESSION_SECRET"} if payload["method"] == "Login" else {"devices": []}
        return web.json_response({"success": True, "data": data})

    url = await server(handler)
    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
        client = SrmClient(AiohttpTransport(session, url, True), "LOGIN_SECRET", "PASSWORD_SECRET")
        assert await client.read("clients") == {"devices": []}
    assert all(method == "POST" and query == "" for method, _, query, _ in calls)
    assert calls[0][3]["passwd"] == "PASSWORD_SECRET"
    assert calls[1][3]["_sid"] == "SESSION_SECRET"


async def test_307_redirect_never_forwards_password(server):
    received = []

    async def destination(request):
        received.append(await request.text())
        return web.json_response({"success": True, "data": {}})

    target = await server(destination)

    async def redirect(request):
        raise web.HTTPTemporaryRedirect(target)

    url = await server(redirect)
    async with aiohttp.ClientSession() as session:
        transport = AiohttpTransport(session, url, True)
        with pytest.raises(TransportError):
            await transport.post("auth.cgi", {"passwd": "SECRET"})
    assert received == []


@pytest.mark.parametrize(
    "body",
    ["<html>SECRET</html>", "[]", "a" * (4 * 1024 * 1024 + 1)],
    ids=["html", "array", "too_large"],
)
async def test_invalid_responses_are_bounded_and_not_leaked(server, body):
    async def handler(request):
        return web.Response(text=body)

    url = await server(handler)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ResponseError) as error:
            await AiohttpTransport(session, url, True).post("entry.cgi", {})
        assert "SECRET" not in str(error.value)


async def test_http_error_does_not_expose_body(server):
    async def handler(request):
        return web.Response(status=500, text=json.dumps({"password": "SECRET"}))

    url = await server(handler)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(TransportError, match="HTTP 500") as error:
            await AiohttpTransport(session, url, True).post("entry.cgi", {})
        assert "SECRET" not in str(error.value)
