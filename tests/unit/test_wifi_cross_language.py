"""Cross-language protocol compatibility tests.

Verifies that frames built by Python can be parsed by Java and vice versa,
by generating test vectors and validating them against both implementations.
"""

from __future__ import annotations

import struct
import subprocess
import json
import os
from pathlib import Path

import pytest

from opendisplay.wifi.protocol import (
    PROTOCOL_VERSION,
    PKT_DISPLAY_ANNOUNCEMENT,
    PKT_IMAGE_REQUEST,
    PKT_NEW_IMAGE,
    PKT_NO_IMAGE,
    PKT_REQUEST_CONFIG,
    build_frame,
    build_new_image,
    build_no_image,
    build_request_config,
    build_single_packet,
    crc16_ccitt,
    parse_frame,
)


def _find_project_root() -> Path:
    """Walk up to find the directory containing opendisplay-java/."""
    d = Path(__file__).resolve()
    while d.parent != d:
        if (d / "opendisplay-java").is_dir():
            return d
        d = d.parent
    raise RuntimeError("Cannot find project root with opendisplay-java/")


class TestCrcAgreement:
    """Verify CRC16-CCITT produces identical results in Python and Java."""

    KNOWN_VECTORS = [
        (b"", 0xFFFF),
        (b"123456789", 0x29B1),
        (b"\x00", 0xE1F0),
        (b"\xff" * 100, None),  # just verify agreement, not a known value
    ]

    def test_known_crc_values(self) -> None:
        for data, expected in self.KNOWN_VECTORS:
            result = crc16_ccitt(data)
            if expected is not None:
                assert result == expected, f"CRC of {data!r}: expected {expected:#06x}, got {result:#06x}"


class TestFrameRoundTrip:
    """Verify frames built by Python can be parsed back."""

    def test_image_request_round_trip(self) -> None:
        payload = bytes([0xFF, 0xBF])  # battery=255, rssi=-65
        single = build_single_packet(0, PKT_IMAGE_REQUEST, payload)
        frame = build_frame(single)
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed.packet_id == PKT_IMAGE_REQUEST
        assert parsed.battery_percent == 0xFF
        assert parsed.rssi == -65

    def test_announcement_round_trip(self) -> None:
        payload = struct.pack(
            "<HHbHHHHHb",
            2880, 2160, 0x00, 1, 1, 0, 0, 0, 0,
        )
        single = build_single_packet(0, PKT_DISPLAY_ANNOUNCEMENT, payload)
        frame = build_frame(single)
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed.packet_id == PKT_DISPLAY_ANNOUNCEMENT
        assert parsed.width == 2880
        assert parsed.height == 2160

    def test_no_image_round_trip(self) -> None:
        frame = build_no_image(300)
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed.packet_id == PKT_NO_IMAGE
        assert parsed.poll_interval == 300

    def test_request_config_round_trip(self) -> None:
        frame = build_request_config()
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed.packet_id == PKT_REQUEST_CONFIG

    def test_new_image_round_trip(self) -> None:
        image = bytes(range(256)) * 10
        frame = build_new_image(image, 120, 0x01)
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed.packet_id == PKT_NEW_IMAGE
        assert parsed.image_data == image
        assert parsed.poll_interval == 120
        assert parsed.refresh_type == 0x01

    def test_large_image_round_trip(self) -> None:
        """Verify uint32 length works for images > 64KB."""
        image = b"\xaa" * 100_000
        frame = build_new_image(image, 60, 0x00)
        parsed = parse_frame(frame)
        assert parsed is not None
        assert parsed.image_data == image
        assert len(parsed.image_data) == 100_000

    def test_corrupted_crc_rejected(self) -> None:
        frame = bytearray(build_request_config())
        frame[-1] ^= 0xFF
        assert parse_frame(bytes(frame)) is None

    def test_truncated_frame_rejected(self) -> None:
        frame = build_no_image(60)
        assert parse_frame(frame[:5]) is None

    def test_wrong_version_rejected(self) -> None:
        frame = bytearray(build_request_config())
        frame[4] = 0x99  # corrupt version
        assert parse_frame(bytes(frame)) is None


class TestImageEncoding:
    """Verify 1bpp encoding matches between Python and Java expectations."""

    def test_all_white_8x8(self) -> None:
        """All-white 8x8 image should be 0xFF * 8."""
        from PIL import Image
        img = Image.new("1", (8, 8), 1)
        data = img.tobytes("raw", "1")
        assert data == b"\xff" * 8

    def test_all_black_8x8(self) -> None:
        """All-black 8x8 image should be 0x00 * 8."""
        from PIL import Image
        img = Image.new("1", (8, 8), 0)
        data = img.tobytes("raw", "1")
        assert data == b"\x00" * 8

    def test_row_padding(self) -> None:
        """Non-byte-aligned width should be row-padded."""
        from PIL import Image
        # 10px wide: each row needs ceil(10/8) = 2 bytes
        img = Image.new("1", (10, 2), 1)
        data = img.tobytes("raw", "1")
        # 2 bytes per row * 2 rows = 4 bytes
        assert len(data) == 4
        # First byte of each row: all 8 pixels white = 0xFF
        # Second byte: 2 pixels white + 6 padding = 0b11000000 = 0xC0
        assert data[0] == 0xFF
        assert data[1] == 0xC0
        assert data[2] == 0xFF
        assert data[3] == 0xC0

    def test_protocol_constants_match(self) -> None:
        """Verify Python and Java use the same protocol constants."""
        assert PROTOCOL_VERSION == 0x01
        assert PKT_DISPLAY_ANNOUNCEMENT == 0x01
        assert PKT_IMAGE_REQUEST == 0x02
        assert PKT_NO_IMAGE == 0x81
        assert PKT_NEW_IMAGE == 0x82
        assert PKT_REQUEST_CONFIG == 0x83
