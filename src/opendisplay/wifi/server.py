"""OpenDisplay WiFi TCP server.

Serves images to OpenDisplay display clients over TCP.
Advertises via mDNS so displays can discover the server automatically.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import struct
from typing import Callable

from .mdns import MdnsAdvertiser
from .protocol import (
    DisplayAnnouncement,
    ImageRequest,
    build_new_image,
    build_no_image,
    build_request_config,
    parse_frame,
)

_LOGGER = logging.getLogger(__name__)


class OpenDisplayServer:
    """Async TCP server implementing the OpenDisplay WiFi protocol.

    Automatically advertises via mDNS so displays can discover it.

    Usage:
        async with OpenDisplayServer(image_data=my_image) as server:
            print(server.actual_port)
            ...
    """

    def __init__(
        self,
        port: int = 0,
        image_data: bytes | None = None,
        poll_interval: int = 60,
        refresh_type: int = 0x00,
        request_config_first: bool = True,
        image_provider: Callable[[DisplayAnnouncement | None], bytes | None] | None = None,
        mdns: bool = True,
        advertise_ip: str | None = None,
    ) -> None:
        self.port = port
        self.image_data = image_data
        self.poll_interval = poll_interval
        self.refresh_type = refresh_type
        self.request_config_first = request_config_first
        self.image_provider = image_provider
        self.mdns_enabled = mdns
        self.advertise_ip = advertise_ip

        self._server: asyncio.AbstractServer | None = None
        self._clients: list[asyncio.Task] = []
        self._mdns: MdnsAdvertiser | None = None
        self.last_announcement: DisplayAnnouncement | None = None
        self.last_image_request: ImageRequest | None = None

    @property
    def actual_port(self) -> int:
        if self._server is not None:
            sockets = self._server.sockets
            if sockets:
                return sockets[0].getsockname()[1]
        return self.port

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self.port
        )
        actual = self.actual_port
        _LOGGER.info("OpenDisplay server listening on port %d", actual)

        if self.mdns_enabled:
            self._mdns = MdnsAdvertiser(actual, self.advertise_ip)
            await self._mdns.start()

    async def stop(self) -> None:
        if self._mdns is not None:
            await self._mdns.stop()
            self._mdns = None

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for task in self._clients:
            task.cancel()
        self._clients.clear()

    async def __aenter__(self) -> OpenDisplayServer:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._clients.append(task)

        addr = writer.get_extra_info("peername")
        _LOGGER.info("Client connected: %s", addr)

        config_received = not self.request_config_first
        last_sent_hash: str | None = None

        try:
            while True:
                frame_data = await self._read_frame(reader)
                if frame_data is None:
                    _LOGGER.info("Client disconnected: %s", addr)
                    break

                parsed = parse_frame(frame_data)
                if parsed is None:
                    _LOGGER.warning("Invalid frame from %s, ignoring", addr)
                    continue

                if isinstance(parsed, ImageRequest):
                    self.last_image_request = parsed
                    _LOGGER.info(
                        "Image request from %s (battery=%d, rssi=%d)",
                        addr, parsed.battery_percent, parsed.rssi,
                    )

                    if not config_received:
                        _LOGGER.info("Requesting config from %s", addr)
                        writer.write(build_request_config())
                        await writer.drain()
                        config_received = True
                        continue

                    loop = asyncio.get_running_loop()
                    image = await loop.run_in_executor(None, self._get_image)

                    # Skip if we already sent this exact image on this connection
                    if image is not None:
                        image_hash = hashlib.sha256(image).hexdigest()[:16]
                        if image_hash == last_sent_hash:
                            image = None
                        else:
                            last_sent_hash = image_hash

                    if image is not None:
                        frame = await loop.run_in_executor(
                            None, build_new_image, image, self.poll_interval, self.refresh_type
                        )
                        _LOGGER.info("Sending image to %s (%d bytes)", addr, len(image))
                        # Write in chunks so cancellation can interrupt
                        mv = memoryview(frame)
                        offset = 0
                        chunk_size = 64 * 1024
                        while offset < len(frame):
                            end = min(offset + chunk_size, len(frame))
                            writer.write(mv[offset:end])
                            await writer.drain()
                            offset = end
                    else:
                        _LOGGER.info("No image for %s", addr)
                        writer.write(build_no_image(self.poll_interval))
                        await writer.drain()

                elif isinstance(parsed, DisplayAnnouncement):
                    self.last_announcement = parsed
                    _LOGGER.info(
                        "Announcement from %s: %dx%d scheme=%d",
                        addr, parsed.width, parsed.height, parsed.colour_scheme,
                    )

                else:
                    _LOGGER.warning("Unexpected packet 0x%02x from %s", parsed.packet_id, addr)

        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.exception("Error handling client %s", addr)
        finally:
            if task is not None and task in self._clients:
                self._clients.remove(task)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _read_frame(self, reader: asyncio.StreamReader) -> bytes | None:
        try:
            len_buf = await reader.readexactly(4)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None

        frame_len = struct.unpack("<I", len_buf)[0]
        if frame_len < 7 or frame_len > 1024 * 1024:
            return None

        try:
            rest = await reader.readexactly(frame_len - 4)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None

        return len_buf + rest

    def _get_image(self) -> bytes | None:
        if self.image_provider is not None:
            return self.image_provider(self.last_announcement)
        return self.image_data
