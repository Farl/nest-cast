# matter-trigger: Trigger the Mac by voice

Emulates a dimmable Matter light on the Mac. Once it is added to Google Home, "Hey Google" can
trigger programs on the Mac, and the brightness (0–100) works as a parameter, so one sentence
can pick between many actions.

```
"Hey Google, set the robot to 30%"
  → Google Assistant (cloud recognition) → Google's Matter controller
  → Matter over the LAN: levelControl.moveToLevelWithOnOff level=76
  → trigger.mjs: converts to 30%, runs config.onTriggerWithLevel
  → nest-cast makes the speaker say "收到，參數 30" (got it, parameter 30)
  → switches itself off after 1.5 s, ready for the next trigger
```

## Running

```bash
npm install
node trigger.mjs        # run outside the Claude Code sandbox: Matter needs inbound mDNS/UDP
```

The first run prints a QR code and a manual pairing code; pair it with Google Home's
"Add → Matter-enabled device". All settings are in [config.json](config.json); events are appended
to `events.jsonl`, one per line.

## Results (2026-11-08, first-generation Google Home Mini as the hub)

| Question | Result |
|---|---|
| Does the app button trigger it? | Yes. Logged within 22 ms of the command arriving |
| Does voice trigger it? | **Yes, after registering the device** (see below) |
| Can it carry a parameter? | Yes. "Set to 30%" arrives as `moveToLevelWithOnOff level=76`, i.e. 30 |
| Trigger to spoken reply | About 4 s (mostly nest-cast start-up and TTS) |
| Does it work offline? | Not tested. Recognition is in the cloud, so probably not |
| End of speech to command arriving | Not measured |

### Pitfalls

- **Unregistered test devices are blocked for voice**: the app can control it, but Assistant
  answers "this device didn't setup yet". Create a project in the
  [Google Home Developer Console](https://console.home.google.com/), add a Matter integration
  (VID `0xFFF1`, PID `0x8000`, matching config.json), re-pair, and voice works.
- **Removing the device in the app may not tell the device**: it still thinks it is paired, so
  scanning the QR code fails. Stop the program, delete `.matter-storage/`, and start it again.
- **"Turn on" carries no brightness**: a plain "turn on" sends only `onOff.on`, while "set to N%"
  is a single command that turns on and sets the level. So after an ON the program waits
  `collectLevelMs` and only counts a level that arrived with it, never a stale one.
- **Trigger phrase**: a routine started by "叫 Claude" ("call Claude") never fired, presumably
  taken as a phone call. "Turn on" + the device name is the most reliable.
- Google adds two fabrics. Fabric #2's admin vendor ID is 0x6006 (Google), and both app and voice
  commands arrive through it, so the Mac cannot tell which one triggered it.

## Limitations

- Numbers only (0–100), no text. Text goes through Google Tasks; see [../tasks-probe/](../tasks-probe/README.md).
- Role in the overall flow: when the doorbell rings, `watch_tasks.py` switches to polling Tasks
  every second. See [../README.md](../README.md).
