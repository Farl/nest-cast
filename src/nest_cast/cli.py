"""Command line entry point: `nest-cast <command> [--name NAME | --host IP]`.

Commands
  discover            list Cast devices on the LAN
  info                device facts from the local setup API (build, Wi-Fi, locale)
  status              volume, mute and the app currently running
  say TEXT            speak TEXT through the speaker (TTS URL fetched by the speaker)
  play URL            play any audio URL the speaker can reach
  play-file PATH      serve a local file from this machine and play it
  volume LEVEL        set volume, 0.0-1.0
  stop                quit whatever app is casting
  trace               print status events for a while (debugging)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as config_mod
from . import device, media


def _with_cast(fn):
    """Wrap a command so it receives a connected cast as its first argument."""
    def run(cfg, args):
        with device.connected(cfg.device, args.name, args.host) as cast:
            return fn(cast, cfg, args)
    return run


def cmd_discover(cfg, args):
    for info in device.discover(cfg.device):
        print(f"{info.friendly_name}\t{info.model_name}\t{info.host}:{info.port}\t{info.cast_type}")


@_with_cast
def cmd_info(cast, cfg, args):
    print(json.dumps(device.eureka_info(cfg.device, cast.cast_info.host), ensure_ascii=False, indent=2))


@_with_cast
def cmd_status(cast, cfg, args):
    s = cast.status
    print(f"name={cast.cast_info.friendly_name} host={cast.cast_info.host}")
    print(f"volume={round(s.volume_level, 3)} muted={s.volume_muted} app={s.display_name}")


def _report(end_state: str) -> int:
    print(f"result={end_state}")
    return 0 if end_state == "FINISHED" else 1


@_with_cast
def cmd_say(cast, cfg, args):
    url = media.tts_url(cfg.tts, args.text, args.lang)
    return _report(media.play_url(cast, cfg.playback, url, cfg.tts.mime, args.volume))


@_with_cast
def cmd_play(cast, cfg, args):
    return _report(media.play_url(cast, cfg.playback, args.url, args.mime, args.volume))


@_with_cast
def cmd_play_file(cast, cfg, args):
    with media.served(cfg.serve, Path(args.path), cast.cast_info.host) as (url, mime):
        return _report(media.play_url(cast, cfg.playback, url, mime, args.volume))


@_with_cast
def cmd_volume(cast, cfg, args):
    cast.set_volume(args.level)
    print(f"volume={args.level}")


@_with_cast
def cmd_stop(cast, cfg, args):
    cast.quit_app()


@_with_cast
def cmd_trace(cast, cfg, args):
    media.trace(cast, args.seconds or cfg.playback.trace_sec)


def _volume_arg(p):
    p.add_argument("--volume", type=float, help="temporary volume 0.0-1.0, restored afterwards")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nest-cast", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help=f"config file (default: ${config_mod.CONFIG_ENV} or config.toml)")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--name", help="device friendly name, e.g. the room name")
    target.add_argument("--host", help="device IP; skips discovery")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("discover").set_defaults(fn=cmd_discover)
    sub.add_parser("info").set_defaults(fn=cmd_info)
    sub.add_parser("status").set_defaults(fn=cmd_status)

    p = sub.add_parser("say")
    p.add_argument("text")
    p.add_argument("--lang", help="TTS language, default from config")
    _volume_arg(p)
    p.set_defaults(fn=cmd_say)

    p = sub.add_parser("play")
    p.add_argument("url")
    p.add_argument("--mime", default="audio/mpeg")
    _volume_arg(p)
    p.set_defaults(fn=cmd_play)

    p = sub.add_parser("play-file")
    p.add_argument("path")
    _volume_arg(p)
    p.set_defaults(fn=cmd_play_file)

    p = sub.add_parser("volume")
    p.add_argument("level", type=float)
    p.set_defaults(fn=cmd_volume)

    sub.add_parser("stop").set_defaults(fn=cmd_stop)

    p = sub.add_parser("trace")
    p.add_argument("--seconds", type=float)
    p.set_defaults(fn=cmd_trace)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = config_mod.load(args.config)
    try:
        return args.fn(cfg, args) or 0
    except device.DeviceNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
