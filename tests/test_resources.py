"""Resource history validation and identity-based mesh joins."""

from types import SimpleNamespace

from component_under_test.resources import mesh_nodes, snapshot


def test_mesh_names_match_ids_not_order_and_keep_clients():
    client = SimpleNamespace(name="Phone", online=True, attributes={"mesh_node_id": 7})
    data = {
        "system_info": {
            "nodes": [
                {"node_id": 0, "model": "RT6600ax"},
                {"node_id": 7, "model": "RT2600ac", "uptime": 30},
            ]
        },
        "ethernet": {
            "nodes": [
                {
                    "node_id": 7,
                    "name": "Bedroom",
                    "eth_ports": [{"port": "LAN1", "link_speed": 100}],
                },
                {"node_id": 0, "name": "Living room"},
            ]
        },
    }
    nodes = mesh_nodes(data, {"client": client})
    assert [n["name"] for n in nodes] == ["Living room", "Bedroom"]
    assert nodes[0]["clients"] == []
    assert nodes[1]["clients"] == [{"name": "Phone", "online": True}]
    assert nodes[1]["ports"] == [{"port": "LAN1", "speed": 100}]


def test_snapshot_missing_values_are_gaps_not_zero():
    empty = snapshot({"utilization": None}, 123)
    assert empty["cpu_total"] is None
    assert empty["ram_usage"] is None
    data = {
        "utilization": {
            "cpu": {"user_load": 3, "system_load": 4, "other_load": 2},
            "memory": {"real_usage": 67},
        }
    }
    assert snapshot(data, 123)["cpu_total"] == 9
    assert snapshot(data, 123)["ram_usage"] == 67
    data["utilization"]["cpu"]["other_load"] = float("nan")
    assert snapshot(data, 123)["cpu_total"] is None
    assert mesh_nodes({"system_info": None, "ethernet": None}, {}) == []
