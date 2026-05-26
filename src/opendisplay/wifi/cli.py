"""CLI for serving images to OpenDisplay devices over WiFi.

Usage:
    opendisplay-serve image.png
    opendisplay-serve https://example.com/dashboard.png
    opendisplay-serve --checkerboard
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Callable
from typing import cast
from urllib.request import urlopen

from PIL import Image

from .imaging import generate_checkerboard, image_to_1bpp
from .protocol import DEFAULT_PORT, DisplayAnnouncement
from .server import OpenDisplayServer


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def _make_image_provider(
    source: str | None, checkerboard: bool
) -> Callable[[DisplayAnnouncement | None], bytes | None]:
    """Create an image_provider.

    For local files: converts once per resolution, caches the result.
    For URLs: fetches and returns raw content each time.
    The server handles deduplication per connection via hashing.
    """
    cache: dict[tuple[int, int], bytes] = {}

    def provider(announcement: DisplayAnnouncement | None) -> bytes | None:
        if announcement is None:
            return None

        width = announcement.width
        height = announcement.height
        key = (width, height)

        if checkerboard:
            if key not in cache:
                cache[key] = generate_checkerboard(width, height)
                logging.info("Generated %dx%d checkerboard: %d bytes", width, height, len(cache[key]))
            return cache[key]

        if source is None:
            return None

        if _is_url(source):
            logging.info("Fetching %s", source)
            try:
                return cast(bytes, urlopen(source, timeout=30).read())
            except Exception:
                logging.exception("Failed to fetch %s", source)
                return None

        else:
            if key not in cache:
                logging.info("Converting %s to %dx%d 1bpp...", source, width, height)
                img = Image.open(source)
                cache[key] = image_to_1bpp(img, width, height)
                logging.info("Image encoded: %d bytes", len(cache[key]))
            return cache[key]

    return provider


async def async_main(args: argparse.Namespace) -> None:
    """Async entry point."""
    provider = _make_image_provider(args.source, args.checkerboard)

    server = OpenDisplayServer(
        port=args.port,
        image_provider=provider,
        poll_interval=args.poll_interval,
        mdns=not args.no_mdns,
        advertise_ip=args.advertise_ip,
    )

    await server.start()
    logging.info("Serving on port %d", server.actual_port)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await server.stop()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Serve images to OpenDisplay devices over WiFi"
    )
    parser.add_argument("source", nargs="?", help="Image file path or URL (http/https)")
    parser.add_argument("--advertise-ip", default=None, help="IP to advertise via mDNS (auto-detected if omitted)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port (default: %(default)s)")
    parser.add_argument("--poll-interval", type=int, default=300, help="Seconds between polls (default: 300)")
    parser.add_argument("--checkerboard", action="store_true", help="Serve a test checkerboard pattern")
    parser.add_argument("--no-mdns", action="store_true", help="Disable mDNS advertisement")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if not args.source and not args.checkerboard:
        parser.error("Provide an image path/URL or use --checkerboard")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass
