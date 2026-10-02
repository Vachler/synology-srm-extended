"""Exportuje jen schéma a explicitně povolené hodnoty, nikdy celé odpovědi."""

import json
import math
from typing import Any

from .models import CLIENT_FIELDS, RAW_METRIC_FIELDS
from .specs import READS

SCHEMA_KEYS = frozenset(CLIENT_FIELDS + RAW_METRIC_FIELDS) | frozenset(
    {
        "data",
        "devices",
        "mac",
        "is_online",
        "is_wireless",
        "cpu",
        "memory",
        "network",
        "system_load",
        "user_load",
        "other_load",
        "1min_load",
        "5min_load",
        "15min_load",
        "real_usage",
        "swap_usage",
        "total_real",
        "avail_real",
        "memory_size",
        "cached",
        "buffer",
        "total_swap",
        "avail_swap",
        "device",
        "rx",
        "tx",
        "time",
        "uptime",
        "model",
        "version",
        "major",
        "minor",
        "build",
        "buildnumber",
        "smallfixnumber",
        "serial",
        "serial_number",
        "hostname",
        "status",
        "ipv4",
        "ipv6",
        "conn_status",
        "ifname",
        "ip",
        "gateway",
        "gatewayip",
        "dns",
        "dns1",
        "dns2",
        "pppoe",
        "list",
        "vpn_profile",
        "netstatus",
        "displayname",
        "enable_priority_check",
        "failed_site_name",
        "failed_site_num",
        "ping_failed_cnt",
        "ping_succ_cnt",
        "enable",
        "enabled",
        "name",
        "id",
        "ssid",
        "channel",
        "bandwidth",
        "width",
        "power",
        "radio",
        "radios",
        "nodes",
        "ports",
        "port",
        "speed",
        "duplex",
        "link",
        "role",
        "type",
        "schedule",
        "unit",
        "units",
        "timestamp",
        "total",
        "count",
        "result",
        "error",
        "code",
        "success",
    }
)
NUMERIC_VALUES = frozenset(
    {
        "system_load",
        "user_load",
        "other_load",
        "1min_load",
        "5min_load",
        "15min_load",
        "real_usage",
        "swap_usage",
        "total_real",
        "avail_real",
        "memory_size",
        "cached",
        "buffer",
        "total_swap",
        "avail_swap",
        "rx",
        "tx",
        *RAW_METRIC_FIELDS,
    }
)
# Pouze předem vyjmenované technické názvy. Libovolné klíče mohou být
# uživatelská jména, SSID, MAC nebo tokeny a zůstávají anonymizované.
SCHEMA_KEYS |= frozenset(
    {
        "eth_ports",
        "eth_port",
        "port_info",
        "port_list",
        "port_status",
        "link_status",
        "link_speed",
        "is_connected",
        "is_enabled",
        "is_up",
        "is_link",
        "is_wan",
        "is_lan",
        "is_primary",
        "is_master",
        "is_router",
        "is_repeater",
        "is_mesh",
        "interface",
        "interfaces",
        "interface_list",
        "interface_name",
        "iflist",
        "lan",
        "wan",
        "ethernet",
        "wifi",
        "wireless",
        "vlan",
        "vlan_id",
        "networks",
        "profiles",
        "profile",
        "settings",
        "config",
        "configuration",
        "radios",
        "radio_list",
        "band_list",
        "bands",
        "frequency",
        "channel_width",
        "tx_power",
        "tx_rate",
        "rx_rate",
        "upload",
        "download",
        "upload_rate",
        "download_rate",
        "upload_speed",
        "download_speed",
        "tx_bytes",
        "rx_bytes",
        "bytes_sent",
        "bytes_received",
        "interval",
        "samples",
        "records",
        "history",
        "tx_packets",
        "rx_packets",
        "tx_errors",
        "rx_errors",
        "dropped",
        "mtu",
        "si_disk",
        "so_disk",
        "subnet",
        "subnet_mask",
        "netmask",
        "dhcp",
        "dhcp_server",
        "dns_server",
        "primary",
        "secondary",
        "mode",
        "enabled",
        "connected",
        "firmware",
        "firmware_version",
        "product",
        "product_name",
        "node_id",
        "node_name",
        "parent_id",
        "parent",
        "children",
        "master",
        "slaves",
        "mesh_nodes",
    }
)
NUMERIC_VALUES |= frozenset(
    {
        "uptime",
        "speed",
        "link_speed",
        "channel",
        "channel_width",
        "frequency",
        "tx_power",
        "tx_rate",
        "rx_rate",
        "upload_rate",
        "download_rate",
        "upload_speed",
        "download_speed",
        "tx_bytes",
        "rx_bytes",
        "bytes_sent",
        "bytes_received",
        "tx_packets",
        "rx_packets",
        "tx_errors",
        "rx_errors",
        "dropped",
        "mtu",
        "si_disk",
        "so_disk",
        "interval",
    }
)
ENUM_VALUES = {
    "conn_status": {"normal", "not available"},
    "netstatus": {"enabled", "disabled", "failed"},
    "unit": {"B/s", "bit/s", "KB/s", "KiB/s", "Mbps", "%", "dBm"},
    "units": {"B/s", "bit/s", "KB/s", "KiB/s", "Mbps", "%", "dBm"},
}
ENUM_VALUES.update(
    {
        "status": {"up", "down", "connected", "disconnected", "normal", "disabled", "enabled"},
        "link_status": {"up", "down", "connected", "disconnected"},
        "duplex": {"full", "half", "unknown"},
        "connection": {"wifi", "ethernet", "wired", "wireless"},
        "band": {"2.4G", "5G", "5G-1", "5G-2", "6G", "2.4GHz", "5GHz", "6GHz"},
        "rate_quality": {"high", "medium", "low"},
    }
)


def _signature(value: Any) -> Any:
    """Číselné hodnoty nezakrývají rozdíly ve struktuře a stavech vzorků."""
    if isinstance(value, dict):
        return {key: _signature(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_signature(item) for item in value]
    if type(value) in (int, float):
        return "<number>"
    return value


def response_shape(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Neznámé klíče mohou být MAC, hostname nebo token: také je anonymizujeme."""
    if depth > 10:
        return "<depth_limit>"
    if isinstance(value, dict):
        result = {}
        for index, (field, item) in enumerate(value.items()):
            if index >= 100:
                result["__truncated__"] = True
                break
            safe_key = field if field in SCHEMA_KEYS else f"__field_{index}__"
            result[safe_key] = response_shape(item, key=safe_key, depth=depth + 1)
        return result
    if isinstance(value, list):
        examples = []
        signatures = set()
        for index, item in enumerate(value[:100]):
            shape = response_shape(item, key=key, depth=depth + 1)
            signature = json.dumps(_signature(shape), sort_keys=True)
            if index < 3 or signature not in signatures:
                examples.append(shape)
                signatures.add(signature)
            if len(examples) >= 6:
                break
        return {
            "__list_length__": len(value),
            "__examples__": examples,
        }
    if value is None:
        return None
    if type(value) is bool:
        return value if key in SCHEMA_KEYS else "<boolean>"
    if type(value) in (int, float):
        if key in NUMERIC_VALUES and math.isfinite(value):
            return value
        return "<number>"
    if isinstance(value, str):
        # JSON uložený ve stringu záměrně nerozbalujeme: mohl by obsahovat autentizaci.
        if value in ENUM_VALUES.get(key, set()):
            return value
        return "<string>"
    return "<unknown>"


def catalog_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for api in sorted({s.api for s in READS} | {"SYNO.API.Auth", "SYNO.API.Info"}):
        meta = catalog.get(api)
        if not isinstance(meta, dict):
            continue
        result[api] = {
            key: meta[key] for key in ("minVersion", "maxVersion") if type(meta.get(key)) is int
        }
    return result


# Pevná technická pole provozu NGFW; identity a IP/MAC zůstávají anonymizované.
SCHEMA_KEYS |= frozenset({"recs", "protocollist", "protocol", "deviceID", "device_id"})
NUMERIC_VALUES |= frozenset({"upload", "download", "upload_rate", "download_rate"})
