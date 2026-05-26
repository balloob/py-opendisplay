"""Tests for the WiFi server CLI image provider."""

from __future__ import annotations

import pytest

from opendisplay.wifi.cli import _make_image_provider
from opendisplay.wifi.protocol import DisplayAnnouncement


class _Response:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data


def _announcement() -> DisplayAnnouncement:
    return DisplayAnnouncement(width=100, height=100)


def test_url_provider_returns_raw_bytes_each_time(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [_Response(b"not an image"), _Response(b"still raw")]
    calls = []

    def fake_urlopen(url: str, timeout: int) -> _Response:
        calls.append((url, timeout))
        return responses.pop(0)

    monkeypatch.setattr("opendisplay.wifi.cli.urlopen", fake_urlopen)

    provider = _make_image_provider("https://example.com/dashboard.bin", checkerboard=False)

    assert provider(_announcement()) == b"not an image"
    assert provider(_announcement()) == b"still raw"
    assert calls == [
        ("https://example.com/dashboard.bin", 30),
        ("https://example.com/dashboard.bin", 30),
    ]


def test_url_provider_returns_no_image_on_fetch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(url: str, timeout: int) -> _Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _Response(b"raw content")
        raise OSError("network unavailable")

    monkeypatch.setattr("opendisplay.wifi.cli.urlopen", fake_urlopen)

    provider = _make_image_provider("https://example.com/dashboard.bin", checkerboard=False)

    assert provider(_announcement()) == b"raw content"
    assert provider(_announcement()) is None
