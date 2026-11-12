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

const oldEndpoint = "https://push.example/old-key";
const newEndpoint = "https://push.example/current-key";
const calls = [];
let currentSubscription = {
  endpoint: oldEndpoint,
  // Some browsers cannot expose the original applicationServerKey.
  options: { applicationServerKey: null },
  async unsubscribe() {
    calls.push("browser-unsubscribe-old");
    currentSubscription = null;
    return true;
  },
};
const newSubscription = {
  endpoint: newEndpoint,
  options: { applicationServerKey: Uint8Array.from([1, 2, 3]).buffer },
  toJSON() { return { endpoint: newEndpoint, keys: { p256dh: "test", auth: "test" } }; },
};
const registration = {
  pushManager: {
    async getSubscription() { return currentSubscription; },
    async subscribe(options) {
      assert.equal(options.userVisibleOnly, true);
      assert.deepEqual([...options.applicationServerKey], [1, 2, 3]);
      calls.push("browser-subscribe-current");
      currentSubscription = newSubscription;
      return newSubscription;
    },
  },
};
const state = {
  watchlistId: "kr-rotation-test",
  pushNotificationConditions: ["recommendation_update"],
  pushNotificationEnabled: false,
};
const context = {
  Uint8Array,
  encodeURIComponent,
  navigator: { serviceWorker: { ready: Promise.resolve(registration) } },
  window: { atob: (value) => Buffer.from(value, "base64").toString("binary") },
  Notification: { permission: "granted" },
  state,
  elements: { pushNotificationButton: {} },
  webPushSupported: () => true,
  pushMarketScope: () => "kr",
  loadPushConfig: async () => ({ enabled: true, public_key: "AQID" }),
  normalizePushNotificationConditions: (values) => values,
  ensureWriteToken: async () => "test-token",
  writeCachedPushEnabled: () => {},
  stopPushNotificationUnreadRefresh: () => {},
  startPushNotificationUnreadRefresh: () => {},
  updatePushNotificationButton: () => {},
  updatePushNotificationDisableButton: () => {},
  setPushNotificationStatus: () => {},
  loadPushNotificationHistory: async () => {},
  fetch: async (url, options = {}) => {
    const method = options.method || "GET";
    if (method === "GET" && url.includes("/status?")) {
      calls.push("server-reports-rotation");
      assert.ok(url.includes(encodeURIComponent(oldEndpoint)));
      return { ok: true, json: async () => ({ enabled: false, key_rotation_required: true, conditions: ["market_ai_signal"] }) };
    }
    if (method === "DELETE") {
      calls.push("server-delete-old");
      assert.equal(JSON.parse(options.body).endpoint, oldEndpoint);
      return { ok: true };
    }
    if (method === "POST") {
      calls.push("server-register-current");
      assert.equal(JSON.parse(options.body).endpoint, newEndpoint);
      assert.deepEqual(JSON.parse(options.body).conditions, ["market_ai_signal"]);
      return { ok: true, json: async () => ({ enabled: true, conditions: ["market_ai_signal"] }) };
    }
    throw new Error(`unexpected request ${method} ${url}`);
  },
};

const selected = [
  extract("function pushApplicationServerKey(value)", "function setPushNotificationStatus("),
  extract("async function currentPushSubscription()", "async function savePushNotificationSettings("),
].join("\n");

(async () => {
  await vm.runInNewContext(`${selected}\nrefreshPushNotificationState();`, context);
  assert.equal(state.pushNotificationEnabled, true);
  assert.deepEqual(calls, [
    "server-reports-rotation",
    "server-delete-old",
    "browser-unsubscribe-old",
    "browser-subscribe-current",
    "server-register-current",
  ]);
  console.log("dashboard VAPID rotation recovered");
})().catch((error) => { console.error(error); process.exitCode = 1; });
