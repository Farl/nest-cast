"""Find, connect to, and inspect Cast speakers.

Two channels are used:
- Cast v2 (TCP 8009, via pychromecast): status, media, volume.
- The speaker's local setup HTTP API (`/setup/eureka_info`, no auth): build, Wi-Fi, locale.
"""
from __future__ import annotations

import json
import urllib.request
from contextlib import contextmanager
from typing import Iterator

import pychromecast

from .config import DeviceConfig

EUREKA_PATH = "/setup/eureka_info"
EUREKA_PARAMS = "version,name,build_info,device_info,net,wifi,setup,settings,opt_in,audio,detail"


class DeviceNotFound(RuntimeError):
    pass


def discover(cfg: DeviceConfig) -> list[pychromecast.CastInfo]:
    """Return the CastInfo of every device that answers mDNS within the discovery timeout.

    Only the info is returned: Chromecast objects from discovery keep resolving through the
    mDNS browser, so they break once it stops. `connected()` reconnects by host instead.
    """
    casts, browser = pychromecast.get_chromecasts(timeout=cfg.discovery_timeout_sec)
    browser.stop_discovery()
    return [c.cast_info for c in casts]


def _find_named(cfg: DeviceConfig, name: str) -> pychromecast.CastInfo | None:
    """Look up one device by friendly name, returning as soon as it answers.

    Unlike discover(), this does not wait out the whole timeout, which matters when a
    speaker is slow to answer mDNS (e.g. while it is busy replying to a voice command).
    """
    infos, browser = pychromecast.discovery.discover_listed_chromecasts(
        friendly_names=[name], discovery_timeout=cfg.discovery_timeout_sec)
    browser.stop_discovery()
    return infos[0] if infos else None


def _pick(cfg: DeviceConfig, name: str | None) -> pychromecast.CastInfo:
    """Choose one device by friendly name, or the only one on the LAN."""
    wanted = name or cfg.default_name
    if wanted:
        info = _find_named(cfg, wanted)
        if info is None:
            raise DeviceNotFound(f"no device named {wanted!r} within {cfg.discovery_timeout_sec}s")
        return info
    infos = discover(cfg)
    found = ", ".join(i.friendly_name for i in infos) or "none"
    if len(infos) != 1:
        raise DeviceNotFound(f"pass --name or --host; found {len(infos)} devices: {found}")
    return infos[0]


@contextmanager
def connected(cfg: DeviceConfig, name: str | None = None, host: str | None = None
              ) -> Iterator[pychromecast.Chromecast]:
    """Connect by explicit host (skips discovery) or by name, and always disconnect."""
    if host:
        target = (host, None, None, None, None)
    else:
        info = _pick(cfg, name)
        target = (info.host, info.port, info.uuid, info.model_name, info.friendly_name)
    cast = pychromecast.get_chromecast_from_host(target)
    cast.wait(timeout=cfg.connect_timeout_sec)
    try:
        yield cast
    finally:
        cast.disconnect()


def eureka_info(cfg: DeviceConfig, host: str) -> dict:
    """Read the speaker's unauthenticated setup API: build, network, locale, opt-ins."""
    url = f"http://{host}:{cfg.setup_http_port}{EUREKA_PATH}?params={EUREKA_PARAMS}"
    with urllib.request.urlopen(url, timeout=cfg.setup_http_timeout_sec) as resp:
        return json.load(resp)
