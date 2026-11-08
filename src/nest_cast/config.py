"""Load config.toml into typed sections. Single source for every tunable value."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_ENV = "NEST_CAST_CONFIG"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"


@dataclass(frozen=True)
class DeviceConfig:
    default_name: str
    discovery_timeout_sec: float
    connect_timeout_sec: float
    setup_http_port: int
    setup_http_timeout_sec: float


@dataclass(frozen=True)
class TtsConfig:
    url_template: str
    lang: str
    mime: str


@dataclass(frozen=True)
class PlaybackConfig:
    wait_limit_sec: float
    poll_interval_sec: float
    trace_sec: float


@dataclass(frozen=True)
class ServeConfig:
    port: int
    mime_by_ext: dict[str, str]


@dataclass(frozen=True)
class Config:
    device: DeviceConfig
    tts: TtsConfig
    playback: PlaybackConfig
    serve: ServeConfig


def load(path: str | os.PathLike | None = None) -> Config:
    """Read the config from `path`, else $NEST_CAST_CONFIG, else the repo's config.toml."""
    path = Path(path or os.environ.get(CONFIG_ENV) or DEFAULT_CONFIG_PATH)
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return Config(
        device=DeviceConfig(**raw["device"]),
        tts=TtsConfig(**raw["tts"]),
        playback=PlaybackConfig(**raw["playback"]),
        serve=ServeConfig(**raw["serve"]),
    )
