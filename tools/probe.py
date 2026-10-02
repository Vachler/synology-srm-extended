"""Lokální čtecí diagnostika SRM; stačí Python 3.12+, bez dalších balíčků."""

import argparse
import asyncio
import getpass
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "synology_srm_extended"))

from srm.client import SrmClient  # noqa: E402
from srm.connection import base_url  # noqa: E402
from srm.errors import (  # noqa: E402
    AuthenticationError,
    CertificateError,
    ResponseError,
    SrmError,
    TransportError,
)
from srm.models import parse_clients, summarize  # noqa: E402
from srm.privacy import catalog_summary, response_shape  # noqa: E402
from srm.specs import READS  # noqa: E402


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StdlibTransport:
    def __init__(self, url: str, verify_ssl: bool = True) -> None:
        context = ssl.create_default_context()
        if not verify_ssl:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self.url = url
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            NoRedirect(),
            urllib.request.HTTPSHandler(context=context),
        )

    async def post(self, path, data):
        return await asyncio.to_thread(self._post, path, data)

    def _post(self, path, data):
        request = urllib.request.Request(
            f"{self.url}/webapi/{path}",
            data=urllib.parse.urlencode(data).encode(),
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                payload = response.read(4 * 1024 * 1024 + 1)
                if len(payload) > 4 * 1024 * 1024:
                    raise ResponseError("Odpověď je příliš velká")
                try:
                    result = json.loads(payload)
                except (ValueError, UnicodeError):
                    raise ResponseError("Router nevrátil JSON") from None
                if not isinstance(result, dict):
                    raise ResponseError("Neplatná odpověď routeru")
                return result
        except urllib.error.HTTPError as err:
            raise TransportError(f"HTTP {err.code}") from None
        except urllib.error.URLError as err:
            if isinstance(err.reason, ssl.SSLCertVerificationError):
                raise CertificateError("Nelze ověřit certifikát") from None
            raise TransportError("Spojení s routerem selhalo") from None
        except (OSError, TimeoutError):
            raise TransportError("Spojení s routerem selhalo") from None


async def collect(client, *, samples: int = 1, delay: float = 2) -> dict:
    report = {
        "format_version": 1,
        "read_only": True,
        "responses": {},
        "note": "Pouze schéma a povolené metriky. Jednotky dosud neověřeny.",
    }
    try:
        await client.discover()
    except AuthenticationError:
        raise
    except SrmError as err:
        report["catalog_status"] = type(err).__name__
    report["api_catalog"] = catalog_summary(client.catalog)
    for spec in READS:
        print(f"Čtení: {spec.key}")
        try:
            raw = await client.read(spec.key)
            if spec.key == "clients":
                try:
                    report["client_counts"] = summarize(parse_clients(raw))
                except ResponseError:
                    report["client_parser"] = "unsupported_response"
            record = {"status": "read_ok", "shape": response_shape(raw)}
            if spec.key in ("utilization", "traffic") and samples > 1:
                record["samples"] = [record.pop("shape")]
                for _ in range(samples - 1):
                    await asyncio.sleep(delay)
                    record["samples"].append(response_shape(await client.read(spec.key)))
            report["responses"][spec.key] = record
        except AuthenticationError:
            raise
        except TransportError as err:
            report["responses"][spec.key] = {"status": type(err).__name__}
            break
        except SrmError as err:
            report["responses"][spec.key] = {
                "status": type(err).__name__,
                "code": getattr(err, "code", None),
            }
    report["capabilities"] = dict(client.capabilities)
    return report


async def run(args, host, username, password):
    url = base_url(host, args.port or (8000 if args.http else 8001), not args.http)
    client = SrmClient(StdlibTransport(url, not args.no_verify), username, password)
    try:
        return await collect(client, samples=args.samples)
    finally:
        await client.logout()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="IP nebo hostname routeru bez protokolu")
    parser.add_argument("--port", type=int, help="Port SRM (HTTPS 8001, HTTP 8000)")
    parser.add_argument("--http", action="store_true", help="Výslovně použít nešifrované HTTP")
    parser.add_argument("--no-verify", action="store_true", help="Výslovně vypnout ověření TLS")
    parser.add_argument("--samples", type=int, choices=(1, 3), default=1)
    parser.add_argument("--output", default="diagnostics-srm.json", help="Očištěný výstup JSON")
    args = parser.parse_args()
    if args.http:
        print("Používáte HTTP: přihlašovací údaje nebudou při přenosu šifrované.")
    if args.no_verify:
        print("Ověření certifikátu je na vaši výslovnou volbu vypnuté.")
    host = args.host or input("IP / hostname routeru: ").strip()
    username = input("Uživatelské jméno SRM: ").strip()
    password = getpass.getpass("Heslo SRM (nezobrazuje se): ")
    try:
        report = asyncio.run(run(args, host, username, password))
        output = Path(args.output)
        # Nepřepisovat existující diagnostiku bez vědomí uživatele.
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print(f"Hotovo: {output.resolve()}")
        return 0
    except AuthenticationError as err:
        print(f"Přihlášení se nezdařilo ({type(err).__name__}, kód {err.code}).")
    except CertificateError:
        print(
            "Certifikát se nepodařilo ověřit. "
            "Zkontrolujte název routeru a důvěryhodnost certifikátu."
        )
    except SrmError as err:
        print(f"Diagnostika se nezdařila: {type(err).__name__}.")
    except FileExistsError:
        print("Výstupní soubor již existuje. Zadejte jiný název pomocí --output.")
    except (ValueError, OSError):
        print("Zkontrolujte adresu, port a možnost zápisu do výstupního souboru.")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDiagnostika byla přerušena.")
        raise SystemExit(130) from None
