"""CLI for serving images to OpenDisplay devices over WiFi.

Usage:
    opendisplay-serve image.png
    opendisplay-serve --checkerboard
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from PIL import Image, ImageOps

from .protocol import DEFAULT_PORT, ParsedFrame
from .server import OpenDisplayServer


def png_to_1bpp(image_path: str, width: int, height: int) -> bytes:
    """Load an image, fit to display, dither to 1-bit, encode as OpenDisplay 1bpp."""
    logging.info("Converting %s to %dx%d 1bpp...", image_path, width, height)
    img = Image.open(image_path).convert("L")
    img = ImageOps.pad(img, (width, height), Image.Resampling.LANCZOS, color=255)
    img = img.convert("1")  # Floyd-Steinberg dither

    bytes_per_row = (width + 7) // 8
    output = bytearray(bytes_per_row * height)

    pixels = img.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y]:
                byte_idx = y * bytes_per_row + x // 8
                bit_idx = 7 - (x % 8)
                output[byte_idx] |= 1 << bit_idx

    logging.info("Image encoded: %d bytes", len(output))
    return bytes(output)


def generate_checkerboard(width: int, height: int, cell_size: int = 8) -> bytes:
    """Generate a 1bpp monochrome checkerboard pattern."""
    logging.info("Generating %dx%d checkerboard...", width, height)
    bytes_per_row = (width + 7) // 8
    output = bytearray(bytes_per_row * height)

    for y in range(height):
        for x in range(width):
            if ((x // cell_size) + (y // cell_size)) % 2 == 1:
                byte_idx = y * bytes_per_row + x // 8
                bit_idx = 7 - (x % 8)
                output[byte_idx] |= 1 << bit_idx

    logging.info("Image encoded: %d bytes", len(output))
    return bytes(output)


def _make_image_provider(
    image_path: str | None, checkerboard: bool
) -> callable:
    """Create an image_provider that converts using the display's announced dimensions."""
    cache: dict[tuple[int, int], bytes] = {}

    def provider(announcement: ParsedFrame | None) -> bytes | None:
        if announcement is None:
            return None

        width = announcement.width
        height = announcement.height
        key = (width, height)

        if key not in cache:
            if image_path:
                cache[key] = png_to_1bpp(image_path, width, height)
            elif checkerboard:
                cache[key] = generate_checkerboard(width, height)
            else:
                return None

        return cache[key]

    return provider


async def async_main(args: argparse.Namespace) -> None:
    """Async entry point."""
    provider = _make_image_provider(args.image, args.checkerboard)

    server = OpenDisplayServer(
        port=args.port,
        image_provider=provider,
        poll_interval=args.poll_interval,
        mdns=not args.no_mdns,
        advertise_ip=args.advertise_ip,
    )

    await server.start()
    logging.info(
        "Serving on port %d. Waiting for display to connect and announce its resolution...",
        server.actual_port,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    await stop_event.wait()
    await server.stop()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Serve images to OpenDisplay devices over WiFi"
    )
    parser.add_argument("image", nargs="?", help="Path to image file (PNG, JPG, etc.)")
    parser.add_argument("--advertise-ip", default=None, help="IP to advertise via mDNS (auto-detected if omitted)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port (default: %(default)s)")
    parser.add_argument("--poll-interval", type=int, default=300, help="Seconds between polls (default: 300)")
    parser.add_argument("--checkerboard", action="store_true", help="Serve a test checkerboard pattern")
    parser.add_argument("--no-mdns", action="store_true", help="Disable mDNS advertisement")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if not args.image and not args.checkerboard:
        parser.error("Provide an image path or use --checkerboard")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    asyncio.run(async_main(args))
    print("Stopped.")
