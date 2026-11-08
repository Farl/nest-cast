# tasks-probe: Voice commands as text, through Google Tasks

Google Assistant saves "remind me to…" into Google Tasks, which makes it a channel for carrying
**free text** from the living room to the Mac.

| File | Purpose |
|---|---|
| [watch_tasks.py](watch_tasks.py) | Polls every list for tasks updated after start-up (`updatedMin`) and prints one JSON line per new task, including `list_id` and `id` |
| [finish_task.py](finish_task.py) | Deletes a task once handled; refuses any task whose title does not start with 機器人, so it can never delete one of my own to-dos |

```bash
export GOOGLE_WORKSPACE_CLI_CONFIG_DIR=~/.config/gws-personal   # the account Google Home uses
python3 watch_tasks.py --poll 5 --fast-poll 1 --fast-for 90
python3 finish_task.py <list_id> <task_id>
```

`watch_tasks.py` also watches `events.jsonl` from [../matter-trigger/](../matter-trigger/README.md):
when the doorbell rings it polls every `--fast-poll` seconds for `--fast-for` seconds.

## Setup

- The personal `gws` account needs the `https://www.googleapis.com/auth/tasks` scope (deleting
  needs write access; read-only is not enough), and the GCP project `gws` uses must have the
  Tasks API enabled.
- If it still reports insufficient scopes after re-authorizing, move `token_cache.json` aside so
  `gws` fetches a fresh token.

## Observations (2026-11-08)

- Tasks land in the **TODO** list (not a separate "Reminders" list). The due field has a date only,
  no time.
- Assistant rewrites the sentence: "提醒我請機器人查明天天氣" (remind me to have the robot check
  tomorrow's weather) becomes "機器人查明天天氣" (robot check tomorrow's weather).
- Google takes a noticeable while between the end of speech and the task appearing; the Mac
  reads it 0.2–2 s after it is created.
- Recognition can be badly wrong ("發文到 Slack" became "撥聞到 snake"). If a command makes no
  sense, ask instead of guessing.
