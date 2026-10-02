"""Validace adresy routeru bez přihlašovacích údajů v URL."""

import ipaddress
import re


def normalize_host(value: str) -> str:
    host = value.strip().strip("[]").lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    if (
        not host
        or len(host) > 253
        or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        )
    ):
        raise ValueError("Zadejte pouze IP nebo hostname, bez URL a portu")
    return host


def base_url(host: str, port: int, https: bool) -> str:
    host = normalize_host(host)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Neplatný port")
    if ":" in host:
        host = f"[{host}]"
    return f"{'https' if https else 'http'}://{host}:{port}"
