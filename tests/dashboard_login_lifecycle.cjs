const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const currentVersion = "20261024v587";
const app = fs.readFileSync("app/static/dashboard/app.js", "utf8");
const worker = fs.readFileSync("app/static/dashboard/dashboard-sw.js", "utf8");

const registrationStart = app.indexOf("function registerDashboardServiceWorker()");
const registrationEnd = app.indexOf("\nlet dashboardVersionCheckPromise", registrationStart);
assert.ok(registrationStart >= 0 && registrationEnd > registrationStart);
const registrationCode = app.slice(registrationStart, registrationEnd);

function controllerChange({ existingController, href }) {
  const handlers = {};
  const replacements = [];
  const serviceWorker = {
    controller: existingController ? {} : null,
    addEventListener(name, handler) { handlers[name] = handler; },
    register() { return { then() { return { catch() {} }; } }; },
  };
  const window = {
    location: { href, replace(url) { replacements.push(url); } },
    setTimeout(callback) { callback(); },
    setInterval() {},
  };
  vm.runInNewContext(
    `${registrationCode}\nregisterDashboardServiceWorker();`,
    {
      navigator: { serviceWorker }, window,
      document: { addEventListener() {} }, URL,
      DASHBOARD_CLIENT_VERSION: currentVersion,
      PRODUCT_SERVICE_WORKER_PATH: "/dashboard-sw.js",
      PRODUCT_SERVICE_WORKER_SCOPE: "/",
    },
  );
  handlers.controllerchange();
  return replacements;
}

assert.deepEqual(controllerChange({
  existingController: false,
  href: "https://secretnote.cloud/dashboard",
}), []);
assert.deepEqual(controllerChange({
  existingController: true,
  href: `https://secretnote.cloud/dashboard?app_build=${currentVersion}`,
}), []);
assert.deepEqual(controllerChange({
  existingController: true,
  href: "https://secretnote.cloud/dashboard?app_build=old",
}), [`https://secretnote.cloud/dashboard?app_build=${currentVersion}`]);

const activationStart = worker.indexOf('self.addEventListener("activate"');
const activationEnd = worker.indexOf('\nself.addEventListener("fetch"', activationStart);
assert.ok(activationStart >= 0 && activationEnd > activationStart);

async function workerActivation() {
  const handlers = {};
  const navigations = [];
  const urls = [
    "https://secretnote.cloud/dashboard",
    "https://secretnote.cloud/dashboard?app_build=old",
    `https://secretnote.cloud/dashboard?app_build=${currentVersion}`,
    "https://secretnote.cloud/other?app_build=old",
  ];
  const clients = urls.map((url) => ({
    url,
    navigate(target) { navigations.push({ url, target }); return Promise.resolve(); },
  }));
  const self = {
    location: { origin: "https://secretnote.cloud" },
    clients: {
      claim() { return Promise.resolve(); },
      matchAll() { return Promise.resolve(clients); },
    },
    addEventListener(name, handler) { handlers[name] = handler; },
  };
  vm.runInNewContext(worker.slice(activationStart, activationEnd), {
    self, caches: { keys() { return Promise.resolve([]); }, delete() { return Promise.resolve(); } },
    URL, Promise, STATIC_CACHE: "test-cache", DASHBOARD_BUILD_VERSION: currentVersion,
  });
  let activation;
  handlers.activate({ waitUntil(promise) { activation = promise; } });
  await activation;
  assert.deepEqual(navigations, [{
    url: "https://secretnote.cloud/dashboard?app_build=old",
    target: `https://secretnote.cloud/dashboard?app_build=${currentVersion}`,
  }]);
}

workerActivation().catch((error) => { console.error(error); process.exitCode = 1; });
