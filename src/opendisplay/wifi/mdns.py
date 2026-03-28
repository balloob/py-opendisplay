"""mDNS advertisement using the system's dns-sd command.

On macOS this goes through mDNSResponder, making the service visible to
Discovery.app, dns-sd -B, and any device on the network. On Linux it
falls back to the Python zeroconf library.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import socket
import sys

_LOGGER = logging.getLogger(__name__)

SERVICE_TYPE = "_opendisplay._tcp"


def _get_local_ip() -> str:
    """Get a non-loopback local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MdnsAdvertiser:
    """Advertise an OpenDisplay TCP service via mDNS."""

    def __init__(self, port: int, advertise_ip: str | None = None) -> None:
        self.port = port
        self.advertise_ip = advertise_ip or _get_local_ip()
        self._process: asyncio.subprocess.Process | None = None
        self._zeroconf: object | None = None
        self._mdns_info: object | None = None

    async def start(self) -> None:
        """Start advertising. Uses dns-sd on macOS, zeroconf elsewhere."""
        if sys.platform == "darwin" and shutil.which("dns-sd"):
            await self._start_dns_sd()
        else:
            await self._start_zeroconf()

    async def stop(self) -> None:
        """Stop advertising."""
        if self._process is not None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

        if self._zeroconf is not None:
            from zeroconf.asyncio import AsyncZeroconf

            zc: AsyncZeroconf = self._zeroconf  # type: ignore[assignment]
            if self._mdns_info is not None:
                await zc.async_unregister_service(self._mdns_info)  # type: ignore[arg-type]
            await zc.async_close()
            self._zeroconf = None
            self._mdns_info = None

    async def _start_dns_sd(self) -> None:
        """Register via macOS dns-sd command (uses system mDNSResponder)."""
        hostname = socket.gethostname().split(".")[0]
        name = f"OpenDisplay Server ({hostname})"

        # dns-sd -R <name> <type> <domain> <port> [<txt>...]
        cmd = [
            "dns-sd", "-R", name, SERVICE_TYPE, "local",
            str(self.port), f"ip={self.advertise_ip}",
        ]
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _LOGGER.info(
            "mDNS: registered '%s' via dns-sd on %s:%d",
            name, self.advertise_ip, self.port,
        )

    async def _start_zeroconf(self) -> None:
        """Register via Python zeroconf (fallback for Linux)."""
        from zeroconf import IPVersion
        from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

        hostname = socket.gethostname()
        addresses = [socket.inet_aton(self.advertise_ip)]

        info = AsyncServiceInfo(
            f"{SERVICE_TYPE}.local.",
            f"OpenDisplay Server ({hostname}).{SERVICE_TYPE}.local.",
            addresses=addresses,
            port=self.port,
            properties={"ip": self.advertise_ip},
        )

        zc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        await zc.async_register_service(info)

        self._zeroconf = zc
        self._mdns_info = info
        _LOGGER.info(
            "mDNS: registered via zeroconf on %s:%d",
            self.advertise_ip, self.port,
        )
