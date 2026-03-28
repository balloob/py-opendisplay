"""OpenDisplay WiFi Basic Standard protocol framing.

Frame format: [length:2 LE][version:1][single_packets...][crc16:2 LE]
Single packet: [number:1][id:1][payload...]
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

PROTOCOL_VERSION = 0x01
DEFAULT_PORT = 2446

# Packet IDs - display -> server
PKT_DISPLAY_ANNOUNCEMENT = 0x01
PKT_IMAGE_REQUEST = 0x02

# Packet IDs - server -> display
PKT_NO_IMAGE = 0x81
PKT_NEW_IMAGE = 0x82
PKT_REQUEST_CONFIG = 0x83


def crc16_ccitt(data: bytes) -> int:
    """CRC16-CCITT: poly 0x1021, init 0xFFFF, no reflection."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def build_frame(*single_packets: bytes) -> bytes:
    """Wrap single packets in an outer frame with length, version, and CRC.

    Frame format: [length:4 LE][version:1][packets...][crc:2]
    """
    packets_data = b"".join(single_packets)
    version_and_packets = bytes([PROTOCOL_VERSION]) + packets_data
    total_len = 4 + len(version_and_packets) + 2
    crc = crc16_ccitt(version_and_packets)
    return struct.pack("<I", total_len) + version_and_packets + struct.pack("<H", crc)


def build_single_packet(number: int, packet_id: int, payload: bytes = b"") -> bytes:
    """Build a single_packet: [number:1][id:1][payload...]."""
    return bytes([number, packet_id]) + payload


# Server -> Display builders

def build_request_config() -> bytes:
    """Build 0x83 request config frame."""
    single = build_single_packet(0, PKT_REQUEST_CONFIG)
    return build_frame(single)


def build_no_image(poll_interval_seconds: int) -> bytes:
    """Build 0x81 no-image frame."""
    payload = struct.pack("<I", poll_interval_seconds)
    single = build_single_packet(0, PKT_NO_IMAGE, payload)
    return build_frame(single)


def build_new_image(
    image_data: bytes,
    poll_interval_seconds: int,
    refresh_type: int = 0x00,
) -> bytes:
    """Build 0x82 new-image frame. Uses uint32 for image_length."""
    payload = struct.pack("<I", len(image_data))
    payload += struct.pack("<I", poll_interval_seconds)
    payload += bytes([refresh_type])
    payload += image_data
    single = build_single_packet(0, PKT_NEW_IMAGE, payload)
    return build_frame(single)


# Frame parsing

@dataclass
class ParsedFrame:
    """Result of parsing an incoming frame."""

    packet_id: int = 0

    # 0x02 image request fields
    battery_percent: int = 0
    rssi: int = 0

    # 0x01 announcement fields
    width: int = 0
    height: int = 0
    colour_scheme: int = 0
    firmware_id: int = 0
    firmware_version: int = 0
    manufacturer_id: int = 0
    model_id: int = 0
    max_compressed_size: int = 0
    rotation: int = 0

    # 0x82 new image fields
    image_data: bytes = field(default_factory=bytes)
    poll_interval: int = 0
    refresh_type: int = 0
    image_length: int = 0


def parse_frame(data: bytes) -> ParsedFrame | None:
    """Parse a complete frame (including length header). Returns None on error."""
    if len(data) < 6:
        return None

    frame_len = struct.unpack_from("<I", data, 0)[0]
    if frame_len != len(data):
        return None

    version = data[4]
    if version != PROTOCOL_VERSION:
        return None

    # Verify CRC
    received_crc = struct.unpack_from("<H", data, len(data) - 2)[0]
    calculated_crc = crc16_ccitt(data[4 : len(data) - 2])
    if received_crc != calculated_crc:
        return None

    # Parse first single packet
    offset = 5  # 4 (length) + 1 (version)
    packets_end = len(data) - 2

    if offset + 2 > packets_end:
        return None

    _packet_number = data[offset]
    offset += 1
    packet_id = data[offset]
    offset += 1

    result = ParsedFrame(packet_id=packet_id)

    if packet_id == PKT_IMAGE_REQUEST:
        if offset + 2 > packets_end:
            return None
        result.battery_percent = data[offset]
        result.rssi = data[offset + 1]
        if result.rssi > 127:
            result.rssi -= 256  # signed byte

    elif packet_id == PKT_DISPLAY_ANNOUNCEMENT:
        if offset + 16 > packets_end:
            return None
        (
            result.width,
            result.height,
        ) = struct.unpack_from("<HH", data, offset)
        offset += 4
        result.colour_scheme = data[offset]
        offset += 1
        (
            result.firmware_id,
            result.firmware_version,
            result.manufacturer_id,
            result.model_id,
            result.max_compressed_size,
        ) = struct.unpack_from("<HHHHH", data, offset)
        offset += 10
        result.rotation = data[offset]

    elif packet_id == PKT_NO_IMAGE:
        if offset + 4 > packets_end:
            return None
        result.poll_interval = struct.unpack_from("<I", data, offset)[0]

    elif packet_id == PKT_NEW_IMAGE:
        if offset + 9 > packets_end:
            return None
        result.image_length = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        result.poll_interval = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        result.refresh_type = data[offset]
        offset += 1
        if offset + result.image_length > packets_end:
            return None
        result.image_data = data[offset : offset + result.image_length]

    elif packet_id == PKT_REQUEST_CONFIG:
        pass

    else:
        return None

    return result
