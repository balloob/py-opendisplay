"""mDNS advertisement for OpenDisplay WiFi servers."""

from __future__ import annotations

import logging
import socket

from zeroconf import InterfaceChoice, IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

_LOGGER = logging.getLogger(__name__)

SERVICE_TYPE = "_opendisplay._tcp"


def _get_local_ip() -> str | None:
    """Get the local IP of the interface that routes to the internet."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


class MdnsAdvertiser:
    """Advertise an OpenDisplay TCP service via mDNS."""

    def __init__(self, port: int, advertise_ip: str | None = None) -> None:
        self.port = port
        self.advertise_ip = advertise_ip
        self._zeroconf: AsyncZeroconf | None = None
        self._info: AsyncServiceInfo | None = None

    async def start(self) -> None:
        """Start advertising via zeroconf."""
        if self.advertise_ip:
            parsed_addresses = [self.advertise_ip]
            interfaces = [self.advertise_ip]
        else:
            local_ip = _get_local_ip()
            parsed_addresses = [local_ip] if local_ip else []
            interfaces = InterfaceChoice.Default

        hostname = socket.gethostname()
        self._info = AsyncServiceInfo(
            f"{SERVICE_TYPE}.local.",
            f"OpenDisplay Server ({hostname}).{SERVICE_TYPE}.local.",
            parsed_addresses=parsed_addresses,
            port=self.port,
            properties={"ip": parsed_addresses[0]} if parsed_addresses else {},
        )

        self._zeroconf = AsyncZeroconf(
            ip_version=IPVersion.V4Only,
            interfaces=interfaces,
        )
        await self._zeroconf.async_register_service(self._info)
        _LOGGER.info(
            "mDNS: advertised %s on %s:%d",
            SERVICE_TYPE,
            self.advertise_ip or "all interfaces",
            self.port,
        )

    async def stop(self) -> None:
        """Stop advertising."""
        if self._zeroconf is not None:
            if self._info is not None:
                await self._zeroconf.async_unregister_service(self._info)
            await self._zeroconf.async_close()
            self._zeroconf = None
            self._info = None
