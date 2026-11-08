"""Watch every Google Tasks list for tasks created/updated after start; print each new one.

Experiment: "Hey Google, 提醒我..." lands in Google Tasks, where the full text can be read.
The Matter doorbell (../matter-trigger) can speed this up: when its event log gets a TRIGGER,
polling switches to a fast interval for a while, so a reminder is picked up within ~1 s.

Uses the gws CLI; pick the Google account with GOOGLE_WORKSPACE_CLI_CONFIG_DIR.

Usage: python watch_tasks.py [--poll 5] [--fast-poll 1] [--fast-for 60] [--trigger-log PATH]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TRIGGER_LOG = Path(__file__).resolve().parent.parent / "matter-trigger" / "events.jsonl"
TRIGGER_EVENT = "TRIGGER"
# How often to check the doorbell log between Tasks polls; cheap local file stat.
TRIGGER_CHECK_SEC = 0.25


def gws(*args: str, params: dict | None = None) -> dict:
    cmd = ["gws", *args]
    if params:
        cmd += ["--params", json.dumps(params)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class DoorbellLog:
    """Detect new TRIGGER lines appended to the matter-trigger event log."""

    def __init__(self, path: Path):
        self.path = path
        self.offset = path.stat().st_size if path.exists() else 0

    def rang(self) -> bool:
        if not self.path.exists():
            return False
        size = self.path.stat().st_size
        if size <= self.offset:
            return False
        with self.path.open(encoding="utf-8") as f:
            f.seek(self.offset)
            new = f.read()
        self.offset = size
        return any(json.loads(l).get("event") == TRIGGER_EVENT for l in new.splitlines() if l.strip())


def poll(lists: list[dict], start: str, seen: set) -> None:
    for tl in lists:
        resp = gws("tasks", "tasks", "list", params={
            "tasklist": tl["id"], "updatedMin": start,
            "showCompleted": True, "showHidden": True, "showAssigned": True})
        if "error" in resp:
            print(f"ERROR {tl['title']}: {resp['error'].get('message', '')[:150]}", flush=True)
        for t in resp.get("items", []):
            key = (t["id"], t.get("updated", ""))
            if key in seen:
                continue
            seen.add(key)
            print(json.dumps({
                "seen_at": now_iso(), "list": tl["title"], "list_id": tl["id"], "id": t["id"],
                "title": t.get("title"), "notes": t.get("notes"), "due": t.get("due"),
                "updated": t.get("updated"), "status": t.get("status"),
            }, ensure_ascii=False), flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--poll", type=float, default=5, help="normal poll interval, seconds")
    p.add_argument("--fast-poll", type=float, default=1, help="poll interval after the doorbell")
    p.add_argument("--fast-for", type=float, default=60, help="seconds to stay fast after the doorbell")
    p.add_argument("--trigger-log", type=Path, default=DEFAULT_TRIGGER_LOG)
    args = p.parse_args()

    start = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    lists = gws("tasks", "tasklists", "list").get("items", [])
    doorbell = DoorbellLog(args.trigger_log)
    print(f"watching {len(lists)} lists for tasks updated after {start}", flush=True)

    seen: set = set()
    fast_until = 0.0
    while True:
        poll(lists, start, seen)
        interval = args.fast_poll if time.time() < fast_until else args.poll
        deadline = time.time() + interval
        while time.time() < deadline:
            if doorbell.rang():
                fast_until = time.time() + args.fast_for
                print(f"DOORBELL {now_iso()} fast polling for {args.fast_for:g}s", flush=True)
                break
            time.sleep(TRIGGER_CHECK_SEC)


if __name__ == "__main__":
    main()
