"""Jednorázové WOL z místní sítě Home Assistantu, bez změn konfigurace routeru."""

import socket

from .srm.models import normalize_mac


def magic_packet(mac: str) -> bytes:
    normalized = normalize_mac(mac)
    if normalized is None:
        raise ValueError("Neplatná MAC")
    return b"\xff" * 6 + bytes.fromhex(normalized.replace(":", "")) * 16


def send_wol(mac: str) -> None:
    packet = magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, ("255.255.255.255", 9))
