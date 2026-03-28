"""Image encoding utilities for OpenDisplay devices.

Provides functions to convert PIL images to 1bpp monochrome format
and generate test patterns.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageOps


def image_to_1bpp(img: Image.Image, width: int, height: int) -> bytes:
    """Fit, dither, and encode a PIL Image as OpenDisplay 1bpp."""
    img = img.convert("L")
    img = ImageOps.pad(img, (width, height), Image.Resampling.LANCZOS, color=255)
    img = img.convert("1")  # Floyd-Steinberg dither
    # PIL raw "1" encoding: packed bits, MSB first, row-padded to byte boundary
    # 0=black, 1=white -- matches OpenDisplay monochrome format
    return img.tobytes("raw", "1")


def generate_checkerboard(width: int, height: int, cell_size: int = 8) -> bytes:
    """Generate a 1bpp monochrome checkerboard pattern.

    Uses PIL for efficient rendering instead of per-pixel Python loops.
    White cells are 1-bits, black cells are 0-bits, MSB first, rows padded
    to byte boundaries -- matching the OpenDisplay monochrome format.
    """
    img = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(img)

    cols = (width + cell_size - 1) // cell_size
    rows = (height + cell_size - 1) // cell_size

    for row in range(rows):
        for col in range(cols):
            if (col + row) % 2 == 1:
                x0 = col * cell_size
                y0 = row * cell_size
                x1 = min(x0 + cell_size, width) - 1
                y1 = min(y0 + cell_size, height) - 1
                draw.rectangle([x0, y0, x1, y1], fill=1)

    return img.tobytes("raw", "1")
