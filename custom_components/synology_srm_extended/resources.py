"""Bounded resource snapshots and mesh records, outside entity attributes."""

import math


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def mapping(value):
    return value if isinstance(value, dict) else {}


def snapshot(data, timestamp):
    utilization = mapping(data.get("utilization"))
    cpu = mapping(utilization.get("cpu"))
    memory = mapping(utilization.get("memory"))
    values = {"time": timestamp}
    for key, field in (
        ("cpu_user", "user_load"),
        ("cpu_system", "system_load"),
        ("cpu_other", "other_load"),
    ):
        v = number(cpu.get(field))
        values[key] = v if v is not None and v <= 100 else None
    parts = [values[k] for k in ("cpu_user", "cpu_system", "cpu_other")]
    values["cpu_total"] = (
        sum(parts) if all(v is not None for v in parts) and sum(parts) <= 100 else None
    )
    for key, field in (("ram_usage", "real_usage"), ("swap_usage", "swap_usage")):
        v = number(memory.get(field))
        values[key] = v if v is not None and v <= 100 else None
    parts = [number(memory.get(k)) for k in ("total_real", "avail_real", "cached", "buffer")]
    values["ram_calculated"] = None
    if all(v is not None for v in parts) and parts[0] > 0 and sum(parts[1:]) <= parts[0]:
        values["ram_calculated"] = round(100 * (parts[0] - sum(parts[1:])) / parts[0], 1)
    return values


def mesh_nodes(data, clients):
    """Join by explicit node IDs; never infer identities from list order."""
    systems = mapping(data.get("system_info")).get("nodes", [])
    ethernet = mapping(data.get("ethernet")).get("nodes", [])
    systems = systems if isinstance(systems, list) else []
    ethernet = ethernet if isinstance(ethernet, list) else []
    indexed = {
        str(n["node_id"]): n
        for n in ethernet
        if isinstance(n, dict) and n.get("node_id") is not None
    }
    output = []
    for node in systems[:64]:
        if not isinstance(node, dict):
            continue
        node_id = node.get("node_id")
        peers = [
            c
            for c in clients.values()
            if node_id is not None and str(c.attributes.get("mesh_node_id")) == str(node_id)
        ]
        ports = indexed.get(str(node_id), {}) if node_id is not None else {}
        name = (
            ports.get("name")
            or node.get("name")
            or next(
                (
                    c.attributes.get("mesh_node_name")
                    for c in peers
                    if c.attributes.get("mesh_node_name")
                ),
                None,
            )
        )
        # The diagnostic confirms a port list but redacts its container key.
        links = [
            p
            for v in ports.values()
            if isinstance(v, list)
            for p in v
            if isinstance(p, dict)
            and isinstance(p.get("port"), str)
            and number(p.get("link_speed")) is not None
        ]
        output.append(
            {
                "id": node_id,
                "name": name,
                "model": node.get("model"),
                "uptime": number(node.get("uptime")),
                "ports": [{"port": p["port"], "speed": p["link_speed"]} for p in links[:16]],
                "clients": [{"name": c.name, "online": c.online} for c in peers[:256]],
            }
        )
    return output
