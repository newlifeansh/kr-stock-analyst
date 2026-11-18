const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../app/static/dashboard/app.js"), "utf8");
class Element {
  constructor(tag, className, textContent = "") {
    Object.assign(this, { tag, className, textContent, children: [], attributes: {}, hidden: false });
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return this.attributes[key] ?? this[key]; }
  addEventListener(type, callback) { this[type] = callback; }
  contains() { return false; }
}
const ids = new Map();
function byId(id) {
  if (id === "domestic-signal-intro") return null;
  if (!ids.has(id)) ids.set(id, new Element("div"));
  return ids.get(id);
}
const requests = [];
const context = vm.createContext({
  URLSearchParams, document: { activeElement: null }, $: byId, PRODUCT_MARKET_UNIVERSE: "kr",
  state: { signalRankingRequest: 0, signalRankingSnapshot: null },
  RECOMMENDATION_LIMIT: 10, AI_SIGNAL_REQUEST_TIMEOUT_MS: 10000,
  el: (...args) => new Element(...args), createStockListLogo: code => ({ code }),
  formatDataBasis: value => value + " 기준",
  fetchRecommendationsForScope: options => new Promise((resolve, reject) => requests.push({ options, resolve, reject })),
});
const helpers = source.slice(source.indexOf("function formatNumber("), source.indexOf("function clampNumber("));
const feature = source.slice(source.indexOf("function isSignalRankingDetail("), source.indexOf("function renderAiSignalsPage("));
vm.runInContext(helpers + feature, context);
const list = byId("signal-ranking-list");
const message = byId("signal-ranking-message");
const retry = byId("signal-ranking-retry");
const time = byId("signal-ranking-asof");
const response = (items, as_of = "2026-11-18T09:30:00+09:00", selection_state = "ready") => ({ items, as_of, selection_state });

(async () => {
  context.PRODUCT_MARKET_UNIVERSE = "us";
  await context.loadSignalRecommendationRanking();
  assert.equal(requests.length, 0);
  context.PRODUCT_MARKET_UNIVERSE = "kr";
  const slow = context.loadSignalRecommendationRanking();
  assert.match(message.textContent, /불러오고/);
  const fresh = context.loadSignalRecommendationRanking({ force: true });
  assert.equal(requests[1].options.limit, 10);
  assert.equal(requests[1].options.candidateLimit, 45);
  const items = [
    { rank: 2, code: "005930", name: "삼성전자", score: "86.48" },
    { rank: 1, code: "000660", name: "SK하이닉스", score: 0 },
    { rank: 3, code: "180640", name: "한진칼", score: null },
  ];
  requests[1].resolve(response(items));
  await fresh;
  const rows = list.children.map(li => li.children[0]);
  assert.deepEqual(rows.map(row => row.children[0].textContent), ["1", "2", "3"]);
  assert.deepEqual(rows.map(row => row.children[3].textContent), ["0점", "86.48점", "—"]);
  assert.equal(rows[1].children[1].code, "005930");
  assert.equal(rows[1].children[2].textContent, "삼성전자");
  assert.equal(rows[1].href, "/dashboard?view=recommend-detail&code=005930&from=signal-ranking");
  requests[0].resolve(response([]));
  await slow;
  assert.equal(list.children.length, 3);
  const asof = time.textContent;
  for (const outcome of ["pending", "error"]) {
    const refresh = context.loadSignalRecommendationRanking();
    if (outcome === "pending") requests.at(-1).resolve(response([], null, "preparing"));
    else requests.at(-1).reject(new Error("offline"));
    await refresh;
    assert.equal(list.children.length, 3);
    assert.equal(time.textContent, asof);
    assert.match(message.textContent, /이전 순위/);
    assert.equal(retry.hidden, false);
  }
  const empty = context.loadSignalRecommendationRanking({ force: true });
  requests.at(-1).resolve(response([], null));
  await empty;
  assert.equal(list.children.length, 0);
  assert.match(message.textContent, /종목이 없어요/);
  assert.equal(time.hidden, true);
  assert.equal(byId("signal-ranking-columns").hidden, true);
  assert.equal(list.attributes["aria-busy"], "false");

  const loader = source.slice(source.indexOf("async function loadRecommendationDetail("), source.indexOf("function openRecommendationDetail("));
  vm.runInContext(loader, context);
  context.state.view = "recommend-detail";
  context.state.recommendationDetailRequest = 0;
  context.window = { location: { search: "?view=recommend-detail&code=005930&from=signal-ranking" }, scrollTo() {} };
  context.elements = { recommendDetailName: new Element("h1"), recommendDetailCode: new Element("span"), recommendDetailContent: new Element("section") };
  context.clearRecommendationDetailItem = () => {};
  const older = context.loadRecommendationDetail("005930");
  const olderResponse = requests.at(-1);
  const newer = context.loadRecommendationDetail("005930");
  requests.at(-1).resolve(response([]));
  await newer;
  olderResponse.resolve(response(items));
  await older;
  assert.match(context.elements.recommendDetailContent.children[0].textContent, /최신 판단 근거를 확인할 수 없어요/);
})().catch(error => { console.error(error); process.exitCode = 1; });
