"""Play audio on a connected speaker: URLs, text-to-speech, and local files.

The speaker always *fetches* media itself. A public URL (including TTS) needs nothing from
this machine; a local file needs an HTTP server here that the speaker can reach inbound.
"""
from __future__ import annotations

import functools
import http.server
import socket
import threading
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pychromecast

from .config import PlaybackConfig, ServeConfig, TtsConfig

ACTIVE_STATES = ("PLAYING", "BUFFERING")
# Port for the UDP route probe in local_ip_facing(); any value works since nothing is sent.
_ROUTE_PROBE_PORT = 1


def tts_url(cfg: TtsConfig, text: str, lang: str | None = None) -> str:
    return cfg.url_template.format(lang=lang or cfg.lang, text=urllib.parse.quote(text))


def play_url(cast: pychromecast.Chromecast, cfg: PlaybackConfig, url: str, mime: str,
             volume: float | None = None) -> str:
    """Play `url`, wait for it to finish, restore the volume, and return the end state.

    Returns the media idle_reason ("FINISHED", "ERROR", ...) or "TIMEOUT".
    """
    original_volume = cast.status.volume_level
    mc = cast.media_controller
    try:
        if volume is not None:
            cast.set_volume(volume)
        mc.play_media(url, mime)
        mc.block_until_active(timeout=cfg.wait_limit_sec)
        return _wait_until_done(mc, cfg)
    finally:
        if volume is not None:
            cast.set_volume(original_volume)
        cast.quit_app()


def _wait_until_done(mc, cfg: PlaybackConfig) -> str:
    deadline = time.time() + cfg.wait_limit_sec
    started = False
    while time.time() < deadline:
        status = mc.status
        if status.player_state in ACTIVE_STATES:
            started = True
        elif status.idle_reason in ("ERROR", "CANCELLED", "INTERRUPTED"):
            return status.idle_reason
        elif started:
            return status.idle_reason or status.player_state
        time.sleep(cfg.poll_interval_sec)
    return "TIMEOUT"


def local_ip_facing(peer: str) -> str:
    """The local IP the OS would use to reach `peer` (no packet is actually sent).

    Probing the speaker itself matters: a generic address may route through a VPN and
    yield an IP the speaker cannot reach.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((peer, _ROUTE_PROBE_PORT))
        return s.getsockname()[0]


@contextmanager
def served(cfg: ServeConfig, file: Path, peer: str) -> Iterator[tuple[str, str]]:
    """Serve `file`'s folder over HTTP for the duration; yield (url, mime) reachable by `peer`."""
    file = file.resolve()
    mime = cfg.mime_by_ext.get(file.suffix.lower())
    if mime is None:
        raise ValueError(f"unsupported extension {file.suffix!r}; add it to [serve.mime_by_ext]")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(file.parent))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", cfg.port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://{local_ip_facing(peer)}:{cfg.port}/{urllib.parse.quote(file.name)}", mime
    finally:
        server.shutdown()


class StatusTracer:
    """Print receiver and media status events; register on a cast and its media controller."""

    def new_cast_status(self, s):
        print(f"[cast ] app={s.display_name} id={s.app_id} vol={round(s.volume_level, 2)}")

    def new_media_status(self, s):
        print(f"[media] state={s.player_state} idle_reason={s.idle_reason}")

    def load_media_failed(self, queue_item_id, error_code):
        print(f"[media] LOAD FAILED item={queue_item_id} code={error_code}")


def trace(cast: pychromecast.Chromecast, seconds: float) -> None:
    tracer = StatusTracer()
    cast.register_status_listener(tracer)
    cast.media_controller.register_status_listener(tracer)
    time.sleep(seconds)
