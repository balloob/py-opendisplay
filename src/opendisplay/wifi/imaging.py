"""Image encoding utilities for OpenDisplay WiFi server."""

from __future__ import annotations

from epaper_dithering import MONO_4_26, DitherMode, dither_image
from PIL import Image, ImageDraw

from ..encoding.images import fit_image
from ..models.enums import FitMode


def image_to_1bpp(
    img: Image.Image,
    width: int,
    height: int,
    dither_mode: DitherMode = DitherMode.FLOYD_STEINBERG,
) -> bytes:
    """Fit, dither, and encode a PIL Image as OpenDisplay 1bpp."""
    fitted = fit_image(img, (width, height), FitMode.CONTAIN)
    dithered = dither_image(fitted, MONO_4_26, mode=dither_mode)
    # Convert palette image to 1-bit and pack with PIL (fast C code)
    return dithered.convert("1").tobytes("raw", "1")


def generate_checkerboard(width: int, height: int, cell_size: int = 8) -> bytes:
    """Generate a 1bpp monochrome checkerboard pattern."""
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
