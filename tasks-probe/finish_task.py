"""Delete a voice-command task once it has been handled, so it never clutters Google Tasks.

Only tasks whose title starts with COMMAND_PREFIX are touched; anything else is refused,
so a wrong id can never delete one of Farl's own to-dos.

Usage: python finish_task.py <tasklist_id> <task_id>
Needs the https://www.googleapis.com/auth/tasks scope (read-only is not enough).
"""
from __future__ import annotations

import json
import subprocess
import sys

# Voice commands are reminders like 「提醒我請機器人…」, which Assistant saves as 「機器人…」.
COMMAND_PREFIX = "機器人"


def gws(*args: str, params: dict) -> dict:
    out = subprocess.run(["gws", *args, "--params", json.dumps(params)],
                         capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else {}


def main(tasklist: str, task: str) -> int:
    ids = {"tasklist": tasklist, "task": task}
    found = gws("tasks", "tasks", "get", params=ids)
    if "error" in found:
        print(f"error: {found['error'].get('message', '')[:200]}", file=sys.stderr)
        return 1
    title = found.get("title", "")
    if not title.startswith(COMMAND_PREFIX):
        print(f"refused: {title!r} does not start with {COMMAND_PREFIX!r}", file=sys.stderr)
        return 2
    resp = gws("tasks", "tasks", "delete", params=ids)
    if "error" in resp:
        print(f"error: {resp['error'].get('message', '')[:200]}", file=sys.stderr)
        return 1
    print(f"deleted: {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
