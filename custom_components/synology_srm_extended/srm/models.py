"""Normalizace pouze doložených klientských polí; neodhaduje jednotky."""

import re
from dataclasses import dataclass
from typing import Any

from .errors import ResponseError

CLIENT_FIELDS = (
    "hostname",
    "ip_addr",
    "ip6_addr",
    "connection",
    "band",
    "wifi_ssid",
    "wifi_profile_name",
    "mesh_node_id",
    "mesh_node_name",
    "network",
    "dev_type",
    "is_guest",
    "is_qos",
    "is_high_qos",
    "is_low_qos",
    "is_beamforming_on",
    "is_manual_dev_type",
    "is_manual_hostname",
)
RAW_METRIC_FIELDS = (
    "signalstrength",
    "rate_quality",
    "current_rate",
    "max_rate",
    "transferRXRate",
    "transferTXRate",
)


def normalize_mac(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    compact = re.sub(r"[:.\-]", "", value.strip()).lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        return None
    if compact == "0" * 12 or int(compact[:2], 16) & 1:
        return None
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2))


def boolean(value: Any) -> bool | None:
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    # Striktní výčet: bool("false") by klienta chybně označilo jako přítomného.
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    return None


def safe_scalar(value: Any) -> bool | int | float | str | None:
    if type(value) in (bool, int, float):
        return value
    if isinstance(value, str):
        return value[:255]
    return None


@dataclass(frozen=True)
class Client:
    mac: str
    online: bool | None
    wireless: bool | None
    attributes: dict[str, Any]

    @property
    def name(self) -> str:
        name = self.attributes.get("hostname")
        return name if isinstance(name, str) and name else self.mac


def parse_clients(data: Any) -> dict[str, Client]:
    # `devices` je doložené ve veřejném SRM klientu. Nehledáme libovolný list rekurzivně.
    if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
        raise ResponseError("Očekáván seznam data.devices; použijte diagnostiku")
    result: dict[str, Client] = {}
    invalid = False
    for item in data["devices"]:
        if not isinstance(item, dict) or (mac := normalize_mac(item.get("mac"))) is None:
            invalid = True
            continue
        attrs = {}
        for key in CLIENT_FIELDS + RAW_METRIC_FIELDS:
            if (value := safe_scalar(item.get(key))) is not None:
                attrs[key] = value
        ipv6 = item.get("ip6_addr")
        if isinstance(ipv6, list):
            attrs["ip6_addr"] = [v[:255] for v in ipv6[:20] if isinstance(v, str)]
        client = Client(
            mac, boolean(item.get("is_online")), boolean(item.get("is_wireless")), attrs
        )
        # Duplicita MAC s protichůdným stavem není bezpečný podklad pro přítomnost.
        previous = result.get(mac)
        if previous is not None and previous.online != client.online:
            raise ResponseError("Rozporné duplicitní klientské záznamy")
        result[mac] = client
    if invalid:
        # Nepublikovat neúplný seznam jako autoritativní nulu nebo hromadné odpojení.
        raise ResponseError("Neplatný klientský záznam; použijte diagnostiku")
    return result


def summarize(clients: dict[str, Client]) -> dict[str, int | None]:
    values = list(clients.values())
    online = [c for c in values if c.online is True]
    complete = all(c.online is not None for c in values)
    result: dict[str, int | None] = {
        "known": len(values),
        "online": len(online) if complete else None,
        "offline": sum(c.online is False for c in values) if complete else None,
    }
    for key, predicate in (
        ("wifi", lambda c: c.wireless),
        ("lan", lambda c: None if c.wireless is None else not c.wireless),
        ("guest", lambda c: boolean(c.attributes.get("is_guest"))),
    ):
        states = [predicate(c) for c in online]
        result[key] = sum(s is True for s in states) if complete and None not in states else None
    return result


class Inventory:
    """Pamatuje identity, ale nepřenáší starý online stav do nového vzorku."""

    def __init__(self) -> None:
        self.known: dict[str, str] = {}
        self.monitored: set[str] = set()
        self.current: dict[str, Client] = {}
        self.hidden: set[str] = set()
        self.views: dict[str, dict] = {}

    def update(self, clients: dict[str, Client], *, create: bool, selected: set[str]) -> bool:
        old = self.serialize()
        self.current = clients
        for mac, client in clients.items():
            if client.name != mac or mac not in self.known:
                self.known[mac] = client.name
        # Výběr řídí uživatel, nikdy online stav nebo objevení nového zařízení.
        self.monitored = set(selected) if create else set()
        return self.serialize() != old

    def serialize(self) -> dict[str, Any]:
        return {
            "known": dict(self.known),
            "monitored": sorted(self.monitored),
            "hidden": sorted(self.hidden),
            "views": {key: dict(value) for key, value in self.views.items()},
        }

    def restore(self, value: Any) -> None:
        if not isinstance(value, dict):
            return
        views = value.get("views", {})
        if isinstance(views, dict):
            self.views = {
                user: clean_view(view)
                for user, view in views.items()
                if isinstance(user, str) and len(user) <= 64 and isinstance(view, dict)
            }
        known = value.get("known", {})
        if isinstance(known, dict):
            for key, name in known.items():
                if (mac := normalize_mac(key)) and isinstance(name, str):
                    self.known[mac] = name[:255]
        monitored = value.get("monitored", [])
        hidden = value.get("hidden", [])
        if isinstance(hidden, list):
            self.hidden = {mac for item in hidden if (mac := normalize_mac(item))}
        if isinstance(monitored, list):
            self.monitored = {m for m in monitored if isinstance(m, str) and m in self.known}


VIEW_CHOICES = {
    "sort": ("name", "state", "ip", "mac", "network", "signal"),
    "filter": ("all", "online", "offline"),
    "visibility": ("visible", "hidden", "all"),
}


def clean_view(value: dict) -> dict:
    return {
        **{
            key: value[key] if value.get(key) in choices else choices[0]
            for key, choices in VIEW_CHOICES.items()
        },
        "descending": value.get("descending") is True,
    }
