"""Pevný seznam čtecích požadavků; žádné obecné spouštění WebAPI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadSpec:
    key: str
    api: str
    version: int = 1
    method: str = "get"
    params: tuple[tuple[str, str], ...] = ()


CLIENTS = ReadSpec("clients", "SYNO.Core.Network.NSM.Device", 5)
READS = (
    CLIENTS,
    ReadSpec(
        "utilization",
        "SYNO.Core.System.Utilization",
        params=(("resource", '["network","cpu","memory"]'),),
    ),
    ReadSpec("connection", "SYNO.Core.Network.Router.ConnectionStatus"),
    ReadSpec("network", "SYNO.Core.Network"),
    ReadSpec("wan_1", "SYNO.Core.Network.Router.Zone.Wan", params=(("number", "1"),)),
    ReadSpec("wan_2", "SYNO.Core.Network.Router.Zone.Wan", params=(("number", "2"),)),
    ReadSpec(
        "gateways",
        "SYNO.Core.Network.Router.Gateway.List",
        params=(
            ("iptype", "all"),
            ("type", "wan"),
        ),
    ),
    ReadSpec("pppoe", "SYNO.Core.Network.PPPoE", 2, "list"),
    ReadSpec(
        "smart_ipv4",
        "SYNO.Core.Network.SmartWAN.Gateway",
        method="list",
        params=(("gatewaytype", "ipv4"),),
    ),
    ReadSpec(
        "smart_ipv6",
        "SYNO.Core.Network.SmartWAN.Gateway",
        method="list",
        params=(("gatewaytype", "ipv6"),),
    ),
    ReadSpec("load_balance", "SYNO.Core.Network.SmartWAN.LoadBalanceInfo"),
    ReadSpec("local_network", "SYNO.Core.Network.LocalNetwork", method="list"),
    ReadSpec("subnet_conflicts", "SYNO.Core.Network.LocalNetwork.SubnetConflictInterfaces"),
    ReadSpec("wifi", "SYNO.Wifi.Network.Setting"),
    ReadSpec("wifi_schedule", "SYNO.Wifi.Network.Schedule.Status"),
    ReadSpec("wifi_button", "SYNO.Wifi.Global.HWButton"),
    ReadSpec("ethernet", "SYNO.Mesh.Network.EthPortInfo"),
    ReadSpec("ports", "SYNO.Core.Network.PortConfStatus"),
    ReadSpec("topology", "SYNO.Core.Network.Router.Topology"),
    ReadSpec(
        "traffic",
        "SYNO.Core.NGFW.Traffic",
        params=(
            ("interval", "live"),
            ("mode", "net"),
        ),
    ),
    # Kandidáti doložení ve veřejném klientu SRM, na cílovém routeru dosud neověření.
    ReadSpec("system_info", "SYNO.Mesh.System.Info"),
    ReadSpec("external_ip", "SYNO.Core.DDNS.ExtIP", method="list"),
)
READ_BY_KEY = {spec.key: spec for spec in READS}
