"""CLI for serving images to OpenDisplay devices over WiFi.

Usage:
    opendisplay-serve image.png
    opendisplay-serve image.png --width 2880 --height 2160
    opendisplay-serve --checkerboard --width 100 --height 100
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from PIL import Image, ImageOps

from .protocol import DEFAULT_PORT
from .server import OpenDisplayServer


def png_to_1bpp(image_path: str, width: int, height: int) -> bytes:
    """Load an image, fit to display, dither to 1-bit, encode as OpenDisplay 1bpp."""
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

    return bytes(output)


def generate_checkerboard(width: int, height: int, cell_size: int = 8) -> bytes:
    """Generate a 1bpp monochrome checkerboard pattern."""
    bytes_per_row = (width + 7) // 8
    output = bytearray(bytes_per_row * height)

    for y in range(height):
        for x in range(width):
            if ((x // cell_size) + (y // cell_size)) % 2 == 1:
                byte_idx = y * bytes_per_row + x // 8
                bit_idx = 7 - (x % 8)
                output[byte_idx] |= 1 << bit_idx

    return bytes(output)


async def async_main(args: argparse.Namespace) -> None:
    """Async entry point."""
    if args.image:
        logging.info("Converting %s to %dx%d 1bpp...", args.image, args.width, args.height)
        image_data = png_to_1bpp(args.image, args.width, args.height)
    else:
        logging.info("Generating %dx%d checkerboard...", args.width, args.height)
        image_data = generate_checkerboard(args.width, args.height)

    logging.info("Image encoded: %d bytes", len(image_data))

    server = OpenDisplayServer(
        port=args.port,
        image_data=image_data,
        poll_interval=args.poll_interval,
        request_config_first=not args.no_config_request,
        mdns=not args.no_mdns,
        advertise_ip=args.advertise_ip,
    )

    await server.start()
    logging.info(
        "Serving on port %d (%dx%d, %d bytes). Waiting for display...",
        server.actual_port,
        args.width,
        args.height,
        len(image_data),
    )

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Serve images to OpenDisplay devices over WiFi"
    )
    parser.add_argument("image", nargs="?", help="Path to image file (PNG, JPG, etc.)")
    parser.add_argument("--advertise-ip", default=None, help="IP to advertise via mDNS (auto-detected if omitted)")
    parser.add_argument("--width", type=int, default=2880, help="Display width (default: 2880)")
    parser.add_argument("--height", type=int, default=2160, help="Display height (default: 2160)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port (default: %(default)s)")
    parser.add_argument("--poll-interval", type=int, default=300, help="Seconds between polls (default: 300)")
    parser.add_argument("--checkerboard", action="store_true", help="Serve a test checkerboard pattern")
    parser.add_argument("--no-config-request", action="store_true", help="Skip requesting display config")
    parser.add_argument("--no-mdns", action="store_true", help="Disable mDNS advertisement")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if not args.image and not args.checkerboard:
        parser.error("Provide an image path or use --checkerboard")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nStopped.")
