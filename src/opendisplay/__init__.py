"""OpenDisplay Protocol Package.

Pure Python package for communicating with OpenDisplay e-paper tags.
Supports BLE (requires bleak + dependencies) and WiFi (no extra dependencies).
"""

from __future__ import annotations

# WiFi subpackage is always available (no external dependencies)
# BLE functionality requires: bleak, pillow, numpy, epaper-dithering, cryptography

try:
    from epaper_dithering import ColorScheme, DitherMode

    from .battery import voltage_to_percent
    from .device import OpenDisplayDevice, prepare_image
    from .discovery import discover_devices
    from .exceptions import (
        AuthenticationError,
        AuthenticationFailedError,
        AuthenticationRequiredError,
        BLEConnectionError,
        BLETimeoutError,
        ConfigParseError,
        ImageEncodingError,
        InvalidResponseError,
        OpenDisplayError,
        ProtocolError,
    )
    from .models.advertisement import (
        AdvertisementData,
        AdvertisementTracker,
        ButtonChangeEvent,
        ButtonEventData,
        decode_button_event,
        parse_advertisement,
    )
    from .models.capabilities import DeviceCapabilities
    from .models.config import (
        BinaryInputs,
        DataBus,
        DisplayConfig,
        GlobalConfig,
        LedConfig,
        ManufacturerData,
        PowerOption,
        SecurityConfig,
        SensorData,
        SystemConfig,
        WifiConfig,
    )
    from .models.enums import (
        BoardManufacturer,
        BusType,
        DIYBoardType,
        FitMode,
        ICType,
        PowerMode,
        RefreshMode,
        Rotation,
        SeeedBoardType,
        WaveshareBoardType,
        get_board_type_name,
        get_manufacturer_name,
    )
    from .models.led_flash import LedFlashConfig, LedFlashStep
    from .protocol import MANUFACTURER_ID, SERVICE_UUID

    _BLE_AVAILABLE = True
except ImportError:
    _BLE_AVAILABLE = False

__version__ = "0.1.0"

__all__ = [
    # Main API
    "OpenDisplayDevice",
    "discover_devices",
    "prepare_image",
    # Exceptions
    "OpenDisplayError",
    "AuthenticationError",
    "AuthenticationFailedError",
    "AuthenticationRequiredError",
    "BLEConnectionError",
    "BLETimeoutError",
    "ProtocolError",
    "ConfigParseError",
    "InvalidResponseError",
    "ImageEncodingError",
    # Models - Config
    "GlobalConfig",
    "SystemConfig",
    "ManufacturerData",
    "PowerOption",
    "DisplayConfig",
    "LedConfig",
    "LedFlashConfig",
    "LedFlashStep",
    "SensorData",
    "DataBus",
    "BinaryInputs",
    "SecurityConfig",
    "WifiConfig",
    # Models - Other
    "DeviceCapabilities",
    "AdvertisementData",
    "AdvertisementTracker",
    "ButtonEventData",
    "ButtonChangeEvent",
    # Enums
    "ColorScheme",
    "DitherMode",
    "FitMode",
    "BoardManufacturer",
    "DIYBoardType",
    "RefreshMode",
    "ICType",
    "PowerMode",
    "BusType",
    "Rotation",
    "SeeedBoardType",
    "WaveshareBoardType",
    "get_board_type_name",
    "get_manufacturer_name",
    # Utilities
    "parse_advertisement",
    "decode_button_event",
    "voltage_to_percent",
    # Constants
    "SERVICE_UUID",
    "MANUFACTURER_ID",
]
