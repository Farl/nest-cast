# nest-cast: Put Claude to work from an old Google Home speaker

Say one sentence to the Google Home Mini in the living room. Claude does the job on the Mac,
reads the result back through the same speaker, then cleans up after itself.

```
"Hey Google, remind me today to have the robot <do something>"
  │  Google Assistant writes the sentence into Google Tasks (title: 機器人<do something>)
  │
  │  (optional) "Hey Google, turn on the robot" ── doorbell: a Matter virtual light that
  │                                                 makes the Mac poll every second
  ▼
tasks-probe/watch_tasks.py   polls Google Tasks for new tasks starting with 機器人 ("robot")
  ▼
Claude session               does the work; outward actions (sending messages, deleting,
                             paying) are confirmed on the computer first
  ▼
nest-cast say                speaks the result on the speaker (long text is split into chunks)
  ▼
tasks-probe/finish_task.py   deletes the task only after the reply was spoken,
                             and only if its title starts with 機器人
```

The command prefix is 機器人 ("robot") because the speaker runs Assistant in Traditional
Chinese, and a Chinese word is recognized far more reliably than "Claude".

## Results (2026-11-08, first-generation Google Home Mini)

| Command as it landed in Tasks | What happened | Time |
|---|---|---|
| 機器人要幫我查一個AI新聞 ("robot, look up an AI news story for me") | Searched the web and read one story aloud | ~70 s from task created to reply finished, mostly spent searching |
| 機器人幫我撥聞到snake說 (garbled) | Meant "post a joke to Slack". Said on the speaker that it didn't understand, confirmed on the computer, DMed the joke to my own Slack, read it aloud, deleted the task | ~34 s after confirming |

- A new task is picked up within one poll interval: 5 s normally, 1 s after the doorbell rings.
- The weakest link is **Assistant's speech recognition**: "發文到 Slack" (post to Slack) became
  "撥聞到 snake". Don't guess at commands that make no sense; ask, and keep the task until done.
- Assistant rewrites the sentence (it drops "remind me to have"), so a fixed prefix is what
  separates commands from my own to-dos.

## Running it

1. **Speaker**: `uv sync`, then check that `uv run nest-cast discover` finds the speaker.
2. **Google Tasks**: the personal `gws` account needs the `https://www.googleapis.com/auth/tasks`
   scope, and its GCP project must have the Tasks API enabled. See [tasks-probe/](tasks-probe/README.md).
3. **Doorbell (optional)**: `cd matter-trigger && npm install && node trigger.mjs`, then pair it in
   the Google Home app. For voice control to work, the test device must first be registered in the
   Google Home Developer Console. See [matter-trigger/](matter-trigger/README.md).
4. **Handler**: in a Claude Code session, watch the output of `watch_tasks.py`. For each task:
   do the work, `say` the result, run `finish_task.py`.

Anything that needs inbound connections (Matter, `play-file`) must run outside the Claude Code sandbox.

## Current limitations

- **A Claude session has to stay open.** The watcher runs as a background job inside the session;
  close it and nobody picks up the reminders, which stay in Tasks. Running unattended would mean
  a service (e.g. launch `claude -p` per task), but then nobody is there to confirm outward
  actions, which needs its own design.
- **The doorbell only carries numbers** (on/off, brightness 0–100). Text has to go through Tasks.
- TTS uses an unofficial Google Translate endpoint that may break at any time; swap
  `[tts].url_template` in `config.toml`.

## Pieces

| Folder / command | Role |
|---|---|
| [`nest-cast`](src/nest_cast/) CLI | The speaker's "mouth": discovery, status, TTS, playback, volume |
| [tasks-probe/](tasks-probe/README.md) | The text channel: watch Google Tasks, delete when handled |
| [matter-trigger/](matter-trigger/README.md) | The doorbell: a Matter virtual light turning voice into an instant trigger with a 0–100 parameter |

### nest-cast CLI

```bash
uv run nest-cast discover                    # list Cast devices on the LAN
uv run nest-cast --name 客廳 status          # volume, current app (客廳 = the speaker's name)
uv run nest-cast --name 客廳 info            # speaker's local setup API: build, Wi-Fi, locale
uv run nest-cast --name 客廳 say "Dinner is ready" --volume 0.3
uv run nest-cast --name 客廳 play https://example.com/a.mp3
uv run nest-cast --name 客廳 play-file ./chime.m4a
uv run nest-cast --name 客廳 volume 0.4
uv run nest-cast --name 客廳 stop
uv run nest-cast --name 客廳 trace           # print status events, for debugging
```

- `--name` returns as soon as the device answers instead of waiting out the timeout;
  `--host <ip>` connects directly and skips discovery.
- `--volume` applies to this playback only; the original volume is restored afterwards.
- Every tunable lives in [config.toml](config.toml): TTS language and chunk size, timeouts,
  ports, file-extension MIME types.

| File | Contents |
|---|---|
| [src/nest_cast/config.py](src/nest_cast/config.py) | Loads `config.toml` |
| [src/nest_cast/device.py](src/nest_cast/device.py) | Discovery, connection, local setup API |
| [src/nest_cast/media.py](src/nest_cast/media.py) | URL playback, TTS (with chunking), local files, status tracing |
| [src/nest_cast/cli.py](src/nest_cast/cli.py) | Command line |

## Background: why not ADB

This started from agent skills that tweak Google TV over ADB: could the same be done to an old Nest?

No. Nest speakers run Cast OS (the Nest Hub runs Fuchsia), with no ADB and no shell, so debloating,
removing apps or swapping launchers is out. What remains is what the LAN exposes, with no Google
account needed:

| Capability | How |
|---|---|
| Find the device | mDNS `_googlecast._tcp` |
| Read device info | Local setup API `http://<ip>:8008/setup/eureka_info`, no auth |
| Status, volume, stop, play a URL, TTS | Cast v2 (TCP 8009); the speaker fetches the audio itself |
| Change system settings, use the microphone | Not possible. So the "ears" go through Google Tasks and Matter instead |

## Pitfalls

- **Sandbox**: the Claude Code sandbox blocks inbound connections, so `play-file` fails with
  `LOAD FAILED` and Matter cannot be paired.
- **VPN**: the URL handed to the speaker by `play-file` must use the local IP on the route to the
  speaker, not the VPN address.
- **Slow mDNS**: while the speaker is busy answering a voice command it may not answer mDNS for
  5 s. Lookups by name return as soon as the device answers and give up after 10 s.
- The doorbell's and Tasks' own pitfalls are in their READMEs.

## Ideas not built yet

- Spoken notice when a Claude Code / ctd job finishes or is waiting for permission
- Announce Unity build and GitLab pipeline results
- Spoken calendar reminders before meetings, a spoken morning brief
