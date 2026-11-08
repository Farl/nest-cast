/**
 * Matter virtual "light" that turns a Google Home routine into a trigger on this Mac.
 *
 * Flow: "Hey Google, ..." -> Google Home routine turns this light ON (optionally at N%)
 *       -> the Home Mini (Matter hub) sends the command over the LAN -> we log it,
 *       run config.onTrigger, then switch back OFF so the next routine fires again.
 *
 * A dimmable light is used instead of a plain switch so the brightness (0-100) can carry
 * a parameter: one device, many possible actions.
 *
 * Needs inbound mDNS/UDP, so run it outside the Claude Code sandbox:  node trigger.mjs
 */
import { readFileSync, appendFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const CONFIG_PATH = process.env.MATTER_TRIGGER_CONFIG ?? resolve(HERE, "config.json");
const cfg = JSON.parse(readFileSync(CONFIG_PATH, "utf8"));

// matter.js reads its storage location from the environment; set it before importing.
process.env.MATTER_STORAGE_PATH ??= resolve(HERE, cfg.storagePath);

const { ServerNode, Endpoint, VendorId } = await import("@matter/main");
const { DimmableLightDevice } = await import("@matter/main/devices/dimmable-light");

/** Matter levelControl range is 1..254; Google Home shows it as a percentage. */
const MAX_LEVEL = 254;
const levelToPercent = (level) => Math.round((level / MAX_LEVEL) * 100);

const LOG_PATH = resolve(HERE, cfg.logPath);
const t0 = Date.now();

/** One JSON line per event; `ms` is milliseconds since start, for latency comparisons. */
function log(event, data = {}) {
  const entry = { at: new Date().toISOString(), ms: Date.now() - t0, event, ...data };
  appendFileSync(LOG_PATH, JSON.stringify(entry) + "\n");
  console.log(`[${entry.at}] ${event}`, Object.keys(data).length ? data : "");
}

/** Run onTriggerWithLevel when the command carried a brightness, else onTrigger. */
function runOnTrigger(percent) {
  const template = percent === null ? cfg.onTrigger : cfg.onTriggerWithLevel;
  if (!template?.length) return;
  const [cmd, ...args] = template.map((a) => a.replaceAll("{percent}", String(percent)));
  const child = spawn(cmd, args, { cwd: HERE, stdio: "inherit" });
  child.on("exit", (code) => log("onTrigger-exit", { code }));
}

const d = cfg.device;
const node = await ServerNode.create({
  id: d.nodeId,
  network: { port: d.port },
  commissioning: { passcode: d.passcode, discriminator: d.discriminator },
  productDescription: { name: d.label, deviceType: DimmableLightDevice.deviceType },
  basicInformation: {
    vendorName: d.vendorName,
    vendorId: VendorId(d.vendorId),
    productName: d.productName,
    productId: d.productId,
    nodeLabel: d.label,
    serialNumber: d.serialNumber,
    uniqueId: d.serialNumber,
  },
});

const light = new Endpoint(DimmableLightDevice, { id: "claude" });
await node.add(light);

let resetting = false;
// Brightness set since the last trigger. A plain "turn on" carries none, so only a level
// that arrives together with the ON counts as the parameter; stale levels are discarded.
let pendingPercent = null;

light.events.onOff.onOff$Changed.on((on) => {
  if (!on) {
    log(resetting ? "reset-off" : "off");
    resetting = false;
    return;
  }
  // "Set to N%" may deliver the level just before or just after the ON; wait to collect it.
  setTimeout(() => {
    const percent = pendingPercent;
    pendingPercent = null;
    log("TRIGGER", { percent });
    runOnTrigger(percent);
  }, cfg.collectLevelMs);
  // Switch back OFF so the same routine can fire again; flag it so it isn't logged as user OFF.
  setTimeout(async () => {
    resetting = true;
    await light.set({ onOff: { onOff: false } });
  }, cfg.resetToOffAfterMs);
});

light.events.levelControl.currentLevel$Changed.on((level) => {
  if (level === null) return;
  pendingPercent = levelToPercent(level);
  log("level", { level, percent: pendingPercent });
});

node.lifecycle.commissioned.on(() => log("commissioned"));
// matter.js itself prints the QR code and manual pairing code while uncommissioned.
node.lifecycle.online.on(() => log("online", { commissioned: node.lifecycle.isCommissioned }));

await node.run();
