"""Diagnostika bez závislostí používá stejné omezené čtení a bezpečný export."""

import importlib.util
import json
from pathlib import Path

import pytest
from aiohttp import web
from srm.client import SrmClient
from srm.errors import TransportError

spec = importlib.util.spec_from_file_location(
    "srm_probe",
    Path(__file__).resolve().parents[1] / "tools" / "probe.py",
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.fixture
async def probe_server():
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


async def test_complete_probe_report_never_contains_credentials_or_addresses(probe_server):
    calls = []

    async def handler(request):
        data = dict(await request.post())
        calls.append(data)
        if data["method"] == "Login":
            result = {"sid": "SID_SECRET"}
        elif data["api"] == "SYNO.API.Info":
            result = {}
        elif data["api"] == "SYNO.Core.Network.NSM.Device":
            result = {
                "devices": [
                    {
                        "mac": "02:11:22:33:44:55",
                        "is_online": True,
                        "hostname": "PRIVATE_PHONE",
                        "password": "EMBEDDED_SECRET",
                    }
                ]
            }
        else:
            result = {"ip": "192.0.2.123", "password": "EMBEDDED_SECRET"}
        return web.json_response({"success": True, "data": result})

    url = await probe_server(handler)
    client = SrmClient(probe.StdlibTransport(url), "USER_SECRET", "PASSWORD_SECRET")
    report = await probe.collect(client, samples=3, delay=0)
    await client.logout()
    serialized = json.dumps(report)
    for secret in (
        "SID_SECRET",
        "PRIVATE_PHONE",
        "EMBEDDED_SECRET",
        "192.0.2.123",
        "USER_SECRET",
        "PASSWORD_SECRET",
        "02:11:22:33:44:55",
    ):
        assert secret not in serialized
    assert report["client_counts"]["online"] == 1
    assert len(report["responses"]["traffic"]["samples"]) == 3
    assert all(data["method"] in {"Login", "Logout", "query", "get", "list"} for data in calls)


async def test_stdlib_transport_does_not_follow_redirects(probe_server):
    received = []

    async def target(request):
        received.append(await request.text())
        return web.json_response({})

    destination = await probe_server(target)

    async def redirect(request):
        raise web.HTTPTemporaryRedirect(destination)

    url = await probe_server(redirect)
    with pytest.raises(TransportError):
        await probe.StdlibTransport(url).post("auth.cgi", {"passwd": "SECRET"})
    assert received == []
