const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(process.argv[2], "utf8");
function extract(start, end) {
  const left = source.indexOf(start);
  const right = source.indexOf(end, left + start.length);
  assert.ok(left >= 0 && right > left, `missing function segment: ${start}`);
  return source.slice(left, right);
}

const oldEndpoint = "https://push.example/desktop-old";
const newEndpoint = "https://push.example/desktop-current";
const calls = [];
let currentSubscription = {
  endpoint: oldEndpoint,
  options: { applicationServerKey: null },
  async unsubscribe() {
    calls.push("browser-unsubscribe-old");
    currentSubscription = null;
    return true;
  },
};
const newSubscription = {
  endpoint: newEndpoint,
  toJSON() { return { endpoint: newEndpoint, keys: { p256dh: "test", auth: "test" } }; },
};
const registration = {
  pushManager: {
    async getSubscription() { return currentSubscription; },
    async subscribe(options) {
      assert.equal(options.userVisibleOnly, true);
      calls.push("browser-subscribe-current");
      currentSubscription = newSubscription;
      return newSubscription;
    },
  },
};
const state = {
  watchlistId: "kr-desktop-rotation",
  desktopPushEnabled: false,
  desktopPushRotationRequired: false,
  desktopPushBusy: false,
  desktopPushConfig: null,
  desktopPushConditions: ["market_ai_signal"],
};
const context = {
  state,
  Notification: { permission: "granted" },
  desktopPushSupported: () => true,
  registerDesktopServiceWorker: async () => registration,
  desktopPushSubscriptionUsesKey: () => true,
  desktopPushApplicationServerKey: () => Uint8Array.from([1, 2, 3]),
  normalizeDesktopPushConditions: (values) => values,
  setDesktopPushMessage: (message) => { state.message = message; },
  paintNotifications: () => {},
  ensureWriteToken: async () => "test-token",
  encodeURIComponent,
  api: async (url) => {
    if (url === "/push/config") return { enabled: true, public_key: "AQID" };
    if (url.includes("/status?")) {
      calls.push("server-reports-rotation");
      return { enabled: false, key_rotation_required: true, conditions: ["market_ai_signal"] };
    }
    throw new Error(`unexpected API ${url}`);
  },
  fetch: async (_url, options) => {
    if (options.method === "DELETE") {
      calls.push("server-delete-old");
      assert.equal(JSON.parse(options.body).endpoint, oldEndpoint);
      return { ok: true };
    }
    if (options.method === "POST") {
      calls.push("server-register-current");
      assert.equal(JSON.parse(options.body).endpoint, newEndpoint);
      return { ok: true, json: async () => ({ enabled: true, conditions: ["market_ai_signal"] }) };
    }
    throw new Error(`unexpected fetch ${options.method}`);
  },
};

const selected = [
  extract("async function refreshDesktopPushState()", "function paintNotifications()"),
  extract("async function saveDesktopPushSettings()", "async function sendDesktopPushTest()"),
].join("\n");

(async () => {
  await vm.runInNewContext(`${selected}\nrefreshDesktopPushState();`, context);
  assert.equal(state.desktopPushRotationRequired, true);
  assert.equal(state.desktopPushEnabled, false);
  assert.ok(state.message.includes("알림 키가 변경"));
  await vm.runInNewContext(`${selected}\nsaveDesktopPushSettings();`, context);
  assert.equal(state.desktopPushEnabled, true);
  assert.equal(state.desktopPushRotationRequired, false);
  assert.deepEqual(calls, [
    "server-reports-rotation",
    "server-delete-old",
    "browser-unsubscribe-old",
    "browser-subscribe-current",
    "server-register-current",
  ]);
  console.log("desktop VAPID rotation recovered");
})().catch((error) => { console.error(error); process.exitCode = 1; });
