"""mDNS advertisement for OpenDisplay WiFi servers."""

from __future__ import annotations

import logging
import socket

from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

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
        self._zeroconf: AsyncZeroconf | None = None
        self._info: AsyncServiceInfo | None = None

    async def start(self) -> None:
        """Start advertising via zeroconf."""
        hostname = socket.gethostname()
        addresses = [socket.inet_aton(self.advertise_ip)]

        self._info = AsyncServiceInfo(
            f"{SERVICE_TYPE}.local.",
            f"OpenDisplay Server ({hostname}).{SERVICE_TYPE}.local.",
            addresses=addresses,
            port=self.port,
            properties={"ip": self.advertise_ip},
        )

        self._zeroconf = AsyncZeroconf(ip_version=IPVersion.V4Only)
        await self._zeroconf.async_register_service(self._info)
        _LOGGER.info(
            "mDNS: advertised %s on %s:%d", SERVICE_TYPE, self.advertise_ip, self.port,
        )

    async def stop(self) -> None:
        """Stop advertising."""
        if self._zeroconf is not None:
            if self._info is not None:
                await self._zeroconf.async_unregister_service(self._info)
            await self._zeroconf.async_close()
            self._zeroconf = None
            self._info = None
