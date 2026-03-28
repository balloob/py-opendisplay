"""Integration tests for the WiFi server - server connects to itself."""

from __future__ import annotations

import asyncio
import struct

import pytest

from opendisplay.wifi.protocol import (
    PKT_DISPLAY_ANNOUNCEMENT,
    PKT_IMAGE_REQUEST,
    PKT_NEW_IMAGE,
    PKT_NO_IMAGE,
    PKT_REQUEST_CONFIG,
    build_frame,
    build_single_packet,
    crc16_ccitt,
    parse_frame,
)
from opendisplay.wifi.server import OpenDisplayServer


def _build_image_request(battery: int = 0xFF, rssi: int = 0) -> bytes:
    """Build an image request frame like a display client would."""
    payload = bytes([battery, rssi & 0xFF])
    single = build_single_packet(0, PKT_IMAGE_REQUEST, payload)
    return build_frame(single)


def _build_announcement(
    width: int = 100, height: int = 100, colour_scheme: int = 0
) -> bytes:
    """Build an announcement frame like a display client would."""
    payload = struct.pack(
        "<HHbHHHHHb", width, height, colour_scheme, 1, 1, 0, 0, 0, 0
    )
    single = build_single_packet(0, PKT_DISPLAY_ANNOUNCEMENT, payload)
    return build_frame(single)


async def _read_frame(reader: asyncio.StreamReader) -> bytes | None:
    """Read a complete frame from the server."""
    len_buf = await asyncio.wait_for(reader.readexactly(2), timeout=5.0)
    frame_len = struct.unpack("<H", len_buf)[0]
    rest = await asyncio.wait_for(reader.readexactly(frame_len - 2), timeout=5.0)
    return len_buf + rest


def _generate_checkerboard(width: int, height: int, cell_size: int = 8) -> bytes:
    """Generate a 1bpp monochrome checkerboard."""
    bytes_per_row = (width + 7) // 8
    output = bytearray(bytes_per_row * height)
    for y in range(height):
        for x in range(width):
            if ((x // cell_size) + (y // cell_size)) % 2 == 1:
                output[y * bytes_per_row + x // 8] |= 1 << (7 - (x % 8))
    return bytes(output)


@pytest.mark.asyncio
async def test_server_config_then_image() -> None:
    """Full flow: connect, get config request, send announcement, get image."""
    image_data = _generate_checkerboard(100, 100)

    async with OpenDisplayServer(
        port=0,
        image_data=image_data,
        poll_interval=60,
        request_config_first=True,
        mdns=False,
    ) as server:
        port = server.actual_port
        assert port > 0

        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        try:
            # 1. Send image request
            writer.write(_build_image_request())
            await writer.drain()

            # 2. Server should respond with config request (0x83)
            frame = await _read_frame(reader)
            parsed = parse_frame(frame)
            assert parsed is not None
            assert parsed.packet_id == PKT_REQUEST_CONFIG

            # 3. Send announcement
            writer.write(_build_announcement(100, 100, 0))
            await writer.drain()

            # 4. Send another image request
            writer.write(_build_image_request())
            await writer.drain()

            # 5. Server should respond with image (0x82)
            frame = await _read_frame(reader)
            parsed = parse_frame(frame)
            assert parsed is not None
            assert parsed.packet_id == PKT_NEW_IMAGE
            assert parsed.image_data == image_data
            assert parsed.poll_interval == 60
            assert parsed.image_length == len(image_data)

        finally:
            writer.close()
            await writer.wait_closed()


@pytest.mark.asyncio
async def test_server_no_config_request() -> None:
    """When request_config_first=False, server sends image immediately."""
    image_data = b"\xff" * 100

    async with OpenDisplayServer(
        port=0,
        image_data=image_data,
        poll_interval=30,
        request_config_first=False,
        mdns=False,
    ) as server:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.actual_port)

        try:
            writer.write(_build_image_request())
            await writer.drain()

            frame = await _read_frame(reader)
            parsed = parse_frame(frame)
            assert parsed is not None
            assert parsed.packet_id == PKT_NEW_IMAGE
            assert parsed.image_data == image_data
        finally:
            writer.close()
            await writer.wait_closed()


@pytest.mark.asyncio
async def test_server_no_image() -> None:
    """When no image data is set, server responds with no-image."""
    async with OpenDisplayServer(
        port=0,
        image_data=None,
        poll_interval=120,
        request_config_first=False,
        mdns=False,
    ) as server:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.actual_port)

        try:
            writer.write(_build_image_request())
            await writer.drain()

            frame = await _read_frame(reader)
            parsed = parse_frame(frame)
            assert parsed is not None
            assert parsed.packet_id == PKT_NO_IMAGE
            assert parsed.poll_interval == 120
        finally:
            writer.close()
            await writer.wait_closed()


@pytest.mark.asyncio
async def test_server_image_provider() -> None:
    """Test dynamic image provider callback."""
    provided_image = b"\xaa\x55" * 50

    def provider(announcement: object) -> bytes:
        return provided_image

    async with OpenDisplayServer(
        port=0,
        image_provider=provider,
        poll_interval=10,
        request_config_first=False,
        mdns=False,
    ) as server:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.actual_port)

        try:
            writer.write(_build_image_request())
            await writer.drain()

            frame = await _read_frame(reader)
            parsed = parse_frame(frame)
            assert parsed is not None
            assert parsed.packet_id == PKT_NEW_IMAGE
            assert parsed.image_data == provided_image
        finally:
            writer.close()
            await writer.wait_closed()


@pytest.mark.asyncio
async def test_multiple_clients() -> None:
    """Server should handle multiple simultaneous clients."""
    image_data = b"\x00" * 50

    async with OpenDisplayServer(
        port=0,
        image_data=image_data,
        poll_interval=5,
        request_config_first=False,
        mdns=False,
    ) as server:
        port = server.actual_port

        async def client_session() -> bytes:
            r, w = await asyncio.open_connection("127.0.0.1", port)
            try:
                w.write(_build_image_request())
                await w.drain()
                frame = await _read_frame(r)
                parsed = parse_frame(frame)
                assert parsed is not None
                return parsed.image_data
            finally:
                w.close()
                await w.wait_closed()

        results = await asyncio.gather(client_session(), client_session(), client_session())
        for result in results:
            assert result == image_data
