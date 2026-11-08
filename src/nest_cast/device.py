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


def _pick(cfg: DeviceConfig, name: str | None) -> pychromecast.CastInfo:
    """Choose one discovered device by friendly name, or the only one on the LAN."""
    infos = discover(cfg)
    found = ", ".join(i.friendly_name for i in infos) or "none"
    wanted = name or cfg.default_name
    if wanted:
        matches = [i for i in infos if i.friendly_name == wanted]
        if not matches:
            raise DeviceNotFound(f"no device named {wanted!r} (found: {found})")
        return matches[0]
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
