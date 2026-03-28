"""OpenDisplay WiFi protocol - TCP server for display devices."""

from .imaging import generate_checkerboard, image_to_1bpp
from .protocol import (
    PROTOCOL_VERSION,
    DEFAULT_PORT,
    ConfigRequest,
    DisplayAnnouncement,
    ImageRequest,
    NewImageResponse,
    NoImageResponse,
    ParsedFrame,
    build_frame,
    build_no_image,
    build_new_image,
    build_request_config,
    crc16_ccitt,
    parse_frame,
)
from .server import OpenDisplayServer

__all__ = [
    "PROTOCOL_VERSION",
    "DEFAULT_PORT",
    "ConfigRequest",
    "DisplayAnnouncement",
    "ImageRequest",
    "NewImageResponse",
    "NoImageResponse",
    "OpenDisplayServer",
    "ParsedFrame",
    "build_frame",
    "build_no_image",
    "build_new_image",
    "build_request_config",
    "crc16_ccitt",
    "generate_checkerboard",
    "image_to_1bpp",
    "parse_frame",
]
