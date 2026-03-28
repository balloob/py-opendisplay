"""CLI entry point: python -m opendisplay.wifi

Starts an OpenDisplay WiFi server that serves a test checkerboard pattern
or a given image file.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .protocol import DEFAULT_PORT
from .server import OpenDisplayServer


def generate_checkerboard(width: int, height: int, cell_size: int = 8) -> bytes:
    """Generate a 1bpp monochrome checkerboard pattern."""
    bytes_per_row = (width + 7) // 8
    output = bytearray(bytes_per_row * height)

    for y in range(height):
        for x in range(width):
            cell_x = x // cell_size
            cell_y = y // cell_size
            is_white = (cell_x + cell_y) % 2 == 1

            if is_white:
                byte_idx = y * bytes_per_row + x // 8
                bit_idx = 7 - (x % 8)
                output[byte_idx] |= 1 << bit_idx

    return bytes(output)


async def main() -> None:
    parser = argparse.ArgumentParser(description="OpenDisplay WiFi server")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="TCP port (default: %(default)s)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument(
        "--width", type=int, default=100, help="Test image width (default: %(default)s)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=100,
        help="Test image height (default: %(default)s)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        help="Poll interval in seconds (default: %(default)s)",
    )
    parser.add_argument("--image", type=str, help="Raw image file to serve")
    parser.add_argument(
        "--no-config-request",
        action="store_true",
        help="Skip requesting display config",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.image:
        with open(args.image, "rb") as f:
            image_data = f.read()
        logging.info("Loaded image: %d bytes from %s", len(image_data), args.image)
    else:
        image_data = generate_checkerboard(args.width, args.height)
        logging.info(
            "Generated %dx%d checkerboard: %d bytes",
            args.width,
            args.height,
            len(image_data),
        )

    server = OpenDisplayServer(
        host=args.host,
        port=args.port,
        image_data=image_data,
        poll_interval=args.poll_interval,
        request_config_first=not args.no_config_request,
    )

    await server.start()
    logging.info("Server running on %s:%d", args.host, server.actual_port)
    logging.info("Press Ctrl+C to stop")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
