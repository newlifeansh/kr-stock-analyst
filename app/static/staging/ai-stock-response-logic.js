/*
 * Secret Note — public per-stock response adapter
 *
 * Only the approved 20-day, 60-day, and supply/demand explanations are built
 * in the browser. Private scoring, thresholds, and source weights stay on the
 * server and are intentionally absent from this bundle.
 */
(function attachAiStockResponseLogic(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SecretNoteAiStockResponse = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function createAiStockResponseLogic() {
  "use strict";

  const VERSION = "20260908-public-reasons-v7";
  const PUBLIC_REASON_KEYS = Object.freeze(["trend_20d", "trend_60d", "flow"]);
  const PUBLIC_REASON_LABELS = Object.freeze({
    trend_20d: "20일",
    trend_60d: "60일",
    flow: "수급",
  });
  const numberFormatter = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
  const usdFormatter = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const number = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const compact = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const unique = (items) => Array.from(new Set(items.filter(Boolean)));
  const newestAsOf = (...values) => values
    .flat(Infinity)
    .filter(Boolean)
    .map((value) => ({ value, timestamp: Date.parse(String(value)) }))
    .filter((item) => Number.isFinite(item.timestamp))
    .sort((left, right) => right.timestamp - left.timestamp)[0]?.value || null;
  const currencyFor = (dashboard = {}) => (
    dashboard.currency === "USD"
    || ["NASDAQ", "NYSE", "SP500", "US"].includes(String(dashboard.market || "").toUpperCase())
      ? "USD"
      : "KRW"
  );
  const roundKrwPrice = (value) => {
    const parsed = number(value);
    if (parsed === null || parsed <= 0) return null;
    const tick = parsed >= 500_000 ? 1_000
      : parsed >= 200_000 ? 500
        : parsed >= 50_000 ? 100
          : parsed >= 20_000 ? 50
            : parsed >= 5_000 ? 10
              : parsed >= 2_000 ? 5
                : 1;
    return Math.max(tick, Math.round(parsed / tick) * tick);
  };
  const roundPrice = (value, currency = "KRW") => {
    const parsed = number(value);
    if (parsed === null || parsed <= 0) return null;
    return currency === "USD" ? Math.round(parsed * 100) / 100 : roundKrwPrice(parsed);
  };
  const priceText = (value, currency = "KRW") => {
    const parsed = number(value);
    if (parsed === null || parsed <= 0) return "가격 자료 부족";
    return currency === "USD"
      ? `$${usdFormatter.format(parsed)}`
      : `${numberFormatter.format(parsed)}원`;
  };
  const percentText = (value) => {
    const parsed = number(value);
    if (parsed === null) return "수익률 계산 전";
    return `${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}%`;
  };

  const normalizeState = (value, available = true) => {
    if (!available) return "unavailable";
    const state = compact(value).toLowerCase();
    if (["positive", "supportive", "approved", "ready", "bullish"].includes(state)) return "positive";
    if (["negative", "caution", "blocked", "risk", "bearish"].includes(state)) return "negative";
    if (["unavailable", "missing", "stale", "limited"].includes(state)) return "unavailable";
    return "neutral";
  };
  const stateFromNumber = (value) => {
    const parsed = number(value);
    if (parsed === null) return "unavailable";
    if (parsed > 0) return "positive";
    if (parsed < 0) return "negative";
    return "neutral";
  };
  const reasonSummary = (key, state) => ({
    trend_20d: {
      positive: "최근 20일 가격 흐름이 우호적입니다.",
      negative: "최근 20일 가격 흐름이 주의 구간입니다.",
      neutral: "최근 20일 가격 흐름의 방향이 뚜렷하지 않습니다.",
      unavailable: "최근 20일 가격 흐름을 확인할 자료가 부족합니다.",
    },
    trend_60d: {
      positive: "20일선과 60일선의 흐름이 우호적입니다.",
      negative: "20일선과 60일선의 흐름이 주의 구간입니다.",
      neutral: "20일선과 60일선의 방향이 뚜렷하지 않습니다.",
      unavailable: "60일 가격 흐름을 확인할 자료가 부족합니다.",
    },
    flow: {
      positive: "최근 수급 흐름이 우호적입니다.",
      negative: "최근 수급 흐름이 주의 구간입니다.",
      neutral: "최근 수급 방향이 뚜렷하지 않습니다.",
      unavailable: "최근 수급을 확인할 자료가 부족합니다.",
    },
  })[key][state];
  const publicReason = (key, state, asOf = null) => ({
    key,
    label: PUBLIC_REASON_LABELS[key],
    state,
    status: {
      positive: "긍정",
      negative: "주의",
      neutral: "뚜렷한 방향 없음",
      unavailable: "자료 확인 중",
    }[state],
    tone: state === "unavailable" ? "limited" : state,
    summary: reasonSummary(key, state),
    evidence: reasonSummary(key, state),
    available: state !== "unavailable",
    asOf,
  });

  const buildPublicReasons = (quant = {}, dashboard = {}) => {
    const supplied = Array.isArray(quant.public_reasons) ? quant.public_reasons : [];
    const suppliedByKey = new Map(supplied.map((item) => [item?.key, item]));
    const factors = Array.isArray(quant.factors) ? quant.factors : [];
    const evidence = Array.isArray(quant.confirmation?.evidence) ? quant.confirmation.evidence : [];
    const factor20 = factors.find((item) => ["trend_20d", "momentum"].includes(item?.key));
    const factor60 = factors.find((item) => ["trend_60d", "trend"].includes(item?.key));
    const flowEvidence = evidence.find((item) => item?.key === "flow");
    const momentum = dashboard.momentum || {};
    const flows = dashboard.flows || {};
    const flowValues = [
      flows.foreign_net_buy_20d,
      flows.institution_net_buy_20d,
      flows.foreign_intensity,
      flows.institution_intensity,
    ].map(number).filter((value) => value !== null);
    const flowValue = flowValues.length
      ? flowValues.reduce((total, value) => total + value, 0)
      : number(momentum.trading_value_change);
    const asOf = quant.price_through || quant.current?.as_of || quant.as_of
      || dashboard.quote?.as_of || dashboard.quote?.trade_date || dashboard.as_of || null;
    const fallback = {
      trend_20d: { item: factor20, state: stateFromNumber(momentum.one_month_return) },
      trend_60d: { item: factor60, state: stateFromNumber(momentum.three_month_return) },
      flow: { item: flowEvidence, state: stateFromNumber(flowValue) },
    };
    return PUBLIC_REASON_KEYS.map((key) => {
      const sourceItem = suppliedByKey.get(key) || fallback[key].item;
      const state = sourceItem
        ? normalizeState(sourceItem.state, sourceItem.available !== false)
        : fallback[key].state;
      return publicReason(key, state, sourceItem?.as_of || asOf);
    });
  };

  const responseDecisionLevels = (dashboard = {}, quant = {}) => {
    const chart = dashboard.chart_analysis || {};
    const current = quant.current || {};
    const currency = currencyFor(dashboard);
    const currentPrice = number(dashboard.quote?.price) ?? number(current.price);
    const levels = Array.isArray(current.levels) ? current.levels : [];
    const levelPrice = (...keys) => number(levels.find(
      (item) => keys.includes(compact(item?.key)),
    )?.price);
    const support = number(chart.support);
    const resistance = number(chart.resistance);
    const base = {
      currency,
      currentPrice: roundPrice(currentPrice, currency),
      changeRate: number(dashboard.quote?.change_rate),
      quoteAsOf: dashboard.quote?.as_of || dashboard.quote?.trade_date || dashboard.as_of || null,
      marketSession: compact(dashboard.quote?.market_session),
      marketSessionLabel: compact(dashboard.quote?.market_session_label),
      quoteIsLive: dashboard.quote?.is_live === true,
      support: roundPrice(support, currency),
      resistance: roundPrice(resistance, currency),
    };
    if (currentPrice === null || currentPrice <= 0) {
      return {
        ...base,
        watchLow: null,
        watchHigh: null,
        buyTrigger: null,
        riskLine: null,
        firstSell: null,
      };
    }
    const below = (candidate, fallback) => {
      const parsed = number(candidate);
      return parsed !== null && parsed < currentPrice ? parsed : fallback;
    };
    const above = (candidate, fallback) => {
      const parsed = number(candidate);
      return parsed !== null && parsed > currentPrice ? parsed : fallback;
    };
    return {
      ...base,
      watchLow: roundPrice(currentPrice * 0.98, currency),
      watchHigh: roundPrice(currentPrice * 0.995, currency),
      buyTrigger: roundPrice(above(levelPrice("entry", "breakout") ?? resistance, currentPrice * 1.02), currency),
      riskLine: roundPrice(below(current.stop_reference ?? levelPrice("stop", "full_exit", "risk") ?? support, currentPrice * 0.97), currency),
      firstSell: roundPrice(above(current.partial_exit_reference ?? current.target_sell_price ?? levelPrice("partial_exit", "target") ?? resistance, currentPrice * 1.05), currency),
      strategyEntryPrice: roundPrice(current.entry_price, currency),
      lockedProfitReference: roundPrice(current.locked_profit_reference, currency),
      signalAction: compact(current.action),
    };
  };

  const guideRow = (key, label, status, value, evidence, tone = "neutral") => ({
    key, label, status, value, evidence, tone,
  });
  const decisionStep = (key, label, status, value, evidence, tone = "neutral") => ({
    key, label, status, value, evidence, tone,
  });
  const investorReason = (result = {}) => (result.publicReasons || [])
    .map((item) => item.summary)
    .join(" ");

  const buildInvestorGuide = (result = {}, {
    investorState = "not_holding",
    averageBuyPrice = null,
  } = {}) => {
    const state = investorState === "holding" ? "holding" : "not_holding";
    const levels = result.decisionLevels || {};
    const currency = levels.currency || "KRW";
    const currentPrice = number(levels.currentPrice);
    const averagePrice = state === "holding" ? number(averageBuyPrice) : null;
    const returnRate = currentPrice !== null && averagePrice !== null && averagePrice > 0
      ? (currentPrice / averagePrice - 1) * 100
      : null;
    const reason = investorReason(result);
    const commonNext = ["20일·60일 가격 흐름과 수급이 같은 방향을 유지하는지"];
    const formatRange = (low, high) => (
      number(low) !== null && number(high) !== null
        ? `${priceText(low, currency)}~${priceText(high, currency)}`
        : "가격 자료 부족"
    );

    if (state === "not_holding") {
      return {
        state,
        positionMode: "watching",
        headline: "현재는 20일·60일·수급을 확인하며 기다릴 때예요",
        summary: "세 가지 공개 흐름이 함께 유지되는지 확인한 뒤 신규 판단을 검토해요.",
        reason,
        direction: "매수 관망",
        directionGuide: "세 가지 공개 흐름을 함께 확인해요",
        currentPrice,
        averageBuyPrice: null,
        returnRate: null,
        holdingStrategy: null,
        rows: [
          guideRow("watch_zone", "눌림목 확인 구간", "하락 멈춤 확인", formatRange(levels.watchLow, levels.watchHigh), "가격이 이 구간에서 안정되는지 확인해요."),
          guideRow("buy_trigger", "상승 흐름 확인선", "매수가 아님", priceText(levels.buyTrigger, currency), "20일·60일 흐름과 수급이 함께 유지되는지 확인하는 선이에요.", "positive"),
          guideRow("risk_line", "관망을 이어갈 기준", "주의", priceText(levels.riskLine, currency), "이 가격 아래에서는 가격 흐름이 더 약해지는지 확인해요.", "negative"),
        ],
        decisionPlan: [
          decisionStep("pullback", "가격이 내려올 때", "하락 멈춤 확인", formatRange(levels.watchLow, levels.watchHigh), "하락이 멈추고 수급이 나아지는지 확인해요."),
          decisionStep("breakout", "가격이 올라갈 때", "매수가 아님", priceText(levels.buyTrigger, currency), "확인선 위에서 20일·60일 흐름과 수급이 유지되는지 확인해요.", "positive"),
          decisionStep("wait", "계속 기다릴 때", "관망 유지", priceText(levels.riskLine, currency), "위험 기준 아래이거나 수급이 약하면 관망을 유지해요.", "negative"),
        ],
        nextChecks: commonNext,
      };
    }

    if (returnRate === null) {
      return {
        state,
        positionMode: "holding_unknown",
        headline: "평균 매수가를 입력하면 내 보유 전략을 볼 수 있어요",
        summary: "아직 내 수익·손실을 계산하지 않았어요. 위에서 평균 매수가를 입력해 주세요.",
        reason: "평균 매수가가 없으면 현재가와 비교할 기준이 없어 수익권·손실권을 구분할 수 없어요.",
        direction: "매수가 입력 필요",
        directionGuide: "내 평균 매수가를 입력해 주세요",
        currentPrice,
        averageBuyPrice: null,
        returnRate: null,
        holdingStrategy: null,
        rows: [],
        decisionPlan: [],
        nextChecks: ["내 평균 매수가를 입력해 현재 수익·손실 구간을 확인하기"],
      };
    }

    const profit = returnRate > 0.5;
    const loss = returnRate < -0.5;
    const protectLine = roundPrice(
      profit && averagePrice < currentPrice
        ? Math.max(averagePrice, number(levels.riskLine) || 0)
        : levels.riskLine,
      currency,
    );
    if (profit) {
      return {
        state,
        positionMode: "holding_profit",
        headline: "현재 수익권이라면 분할 매도로 이익을 지킬 구간을 볼 때예요",
        summary: "가격 기준과 20일·60일·수급 변화를 함께 확인해요.",
        reason,
        direction: "수익 관리",
        directionGuide: "분할 매도와 이익 보호 기준을 함께 봐요",
        currentPrice,
        averageBuyPrice: averagePrice,
        returnRate,
        holdingStrategy: {
          stage: "수익 관리",
          action: "분할 매도 · 이익 보호",
          summary: `현재는 수익권이에요. ${priceText(levels.firstSell, currency)} 부근의 수익 관리와 ${priceText(protectLine, currency)} 아래의 보호 기준을 확인해요.`,
          averageBuyPrice: averagePrice,
          currentPrice,
          returnRate,
        },
        rows: [
          guideRow("return", "내 수익률", "수익권", percentText(returnRate), `평균 매수가 ${priceText(averagePrice, currency)}과 현재가 ${priceText(currentPrice, currency)}을 비교했어요.`, "positive"),
          guideRow("first_sell", "1차 분할 매도 참고선", "수익 관리", priceText(levels.firstSell, currency), "이 가격 부근에서 일부 이익을 지킬지 검토해요.", "positive"),
          guideRow("protect", "이익 보호 기준", "주의", priceText(protectLine, currency), "이 기준 아래에서 수급도 약해지는지 확인해요.", "negative"),
        ],
        decisionPlan: [
          decisionStep("take_profit", "가격이 더 오르면", "일부 매도 검토", priceText(levels.firstSell, currency), "일부 이익을 지킬지 검토해요.", "positive"),
          decisionStep("protect_profit", "가격이 다시 내려오면", "보유 기준 재점검", priceText(protectLine, currency), "가격과 수급이 함께 약해지는지 확인해요.", "negative"),
          decisionStep("keep_holding", "계속 보유하려면", "흐름 유지 확인", `${priceText(protectLine, currency)} 위 유지`, "20일·60일 흐름과 수급이 유지되는지 확인해요."),
        ],
        nextChecks: unique([`${priceText(levels.firstSell, currency)} 부근에서 수익 관리가 필요한지`, ...commonNext]),
      };
    }

    if (loss) {
      return {
        state,
        positionMode: "holding_loss",
        headline: "현재 손실권이라면 가격별 손실 제한 기준을 먼저 세울 때예요",
        summary: "가격 기준과 20일·60일·수급 변화를 함께 확인해요.",
        reason,
        direction: "손실 관리",
        directionGuide: "손실 제한선과 회복 확인선을 나눠 봐요",
        currentPrice,
        averageBuyPrice: averagePrice,
        returnRate,
        holdingStrategy: {
          stage: "손실 관리",
          action: "손실 제한 · 회복 확인",
          summary: `현재는 손실권이에요. ${priceText(levels.riskLine, currency)} 아래의 손실 제한과 ${priceText(levels.buyTrigger, currency)} 위의 회복 흐름을 확인해요.`,
          averageBuyPrice: averagePrice,
          currentPrice,
          returnRate,
        },
        rows: [
          guideRow("return", "내 수익률", "손실권", percentText(returnRate), `평균 매수가 ${priceText(averagePrice, currency)}과 현재가 ${priceText(currentPrice, currency)}을 비교했어요.`, "negative"),
          guideRow("risk_line", "손실 제한 참고선", "주의", priceText(levels.riskLine, currency), "이 가격 아래에서 수급도 약해지는지 확인해요.", "negative"),
          guideRow("recovery", "회복 확인 가격", "조건 확인", priceText(levels.buyTrigger, currency), "20일·60일 흐름과 수급이 함께 회복하는지 확인해요.", "positive"),
        ],
        decisionPlan: [
          decisionStep("limit_loss", "가격이 더 내려가면", "손실 제한 검토", priceText(levels.riskLine, currency), "가격과 수급이 함께 약해지는지 확인해요.", "negative"),
          decisionStep("recovery", "가격이 회복하면", "회복 여부 확인", priceText(levels.buyTrigger, currency), "20일·60일 흐름과 수급이 함께 회복하는지 확인해요.", "positive"),
          decisionStep("hold_loss", "계속 보유하려면", "조건 동시 확인", "가격·수급 함께 확인", "가격 흐름과 수급 방향이 같은지 확인해요."),
        ],
        nextChecks: unique([`${priceText(levels.riskLine, currency)} 아래로 밀리는지`, ...commonNext]),
      };
    }

    return {
      state,
      positionMode: "holding_flat",
      headline: "현재는 본전권이라 보유 기준과 위험선을 함께 확인할 때예요",
      summary: "작은 등락보다 20일·60일 흐름과 수급 변화를 먼저 봐요.",
      reason,
      direction: "보유 기준 확인",
      directionGuide: "위험선과 수익 관리 가격을 함께 봐요",
      currentPrice,
      averageBuyPrice: averagePrice,
      returnRate,
      holdingStrategy: {
        stage: "보유 기준 확인",
        action: "보유 유지 · 위험 기준",
        summary: `현재는 본전권이에요. ${priceText(levels.riskLine, currency)} 아래의 위험과 ${priceText(levels.firstSell, currency)} 부근의 수익 관리를 확인해요.`,
        averageBuyPrice: averagePrice,
        currentPrice,
        returnRate,
      },
      rows: [
        guideRow("return", "내 수익률", "본전권", percentText(returnRate), `평균 매수가 ${priceText(averagePrice, currency)}과 현재가 ${priceText(currentPrice, currency)}을 비교했어요.`),
        guideRow("risk_line", "위험 관리 기준", "주의", priceText(levels.riskLine, currency), "이 가격 아래로 밀리면 수급도 함께 확인해요.", "negative"),
        guideRow("first_sell", "수익 관리 참고선", "조건 확인", priceText(levels.firstSell, currency), "이 가격에 가까워지면 일부 이익을 지킬지 검토해요.", "positive"),
      ],
      decisionPlan: [
        decisionStep("flat_down", "가격이 내려가면", "보유 기준 재점검", priceText(levels.riskLine, currency), "가격과 수급이 함께 약해지는지 확인해요.", "negative"),
        decisionStep("flat_up", "가격이 올라가면", "일부 매도 검토", priceText(levels.firstSell, currency), "수익권으로 바뀌면 일부 이익을 지킬지 검토해요.", "positive"),
        decisionStep("flat_hold", "계속 보유하려면", "수급 확인", "가격·수급 함께 확인", "20일·60일 흐름과 수급이 유지되는지 확인해요."),
      ],
      nextChecks: commonNext,
    };
  };

  const buildResponse = ({ code = "", fallbackDetail = {}, quant = null, dashboard = null } = {}) => {
    const safeQuant = quant && typeof quant === "object" ? quant : {};
    const safeDashboard = dashboard && typeof dashboard === "object" ? dashboard : {};
    const publicReasons = buildPublicReasons(safeQuant, safeDashboard);
    const available = publicReasons.filter((item) => item.available);
    const positiveCount = publicReasons.filter((item) => item.state === "positive").length;
    const negativeCount = publicReasons.filter((item) => item.state === "negative").length;
    const limited = available.length < PUBLIC_REASON_KEYS.length;
    const conflict = positiveCount > 0 && negativeCount > 0;
    const canonicalLabel = compact(safeQuant.current?.label);
    const stance = canonicalLabel || (limited
      ? "정보 확인 우선"
      : positiveCount > negativeCount
        ? "긍정 관찰"
        : negativeCount > positiveCount
          ? "보수 관찰"
          : "중립 관찰");
    const tone = limited ? "limited"
      : positiveCount > negativeCount ? "positive"
        : negativeCount > positiveCount ? "negative" : "neutral";
    return {
      version: VERSION,
      code: compact(code || safeQuant.code || safeDashboard.code || fallbackDetail.code),
      name: compact(safeQuant.name || safeDashboard.name || fallbackDetail.name) || "관심종목",
      asOf: newestAsOf(
        safeQuant.as_of,
        safeDashboard.as_of,
        safeDashboard.quote?.as_of,
        publicReasons.map((item) => item.asOf),
      ),
      stance,
      tone,
      action: "20일·60일 가격 흐름과 수급 변화를 함께 확인하세요.",
      summary: "세부 계산식과 점수는 공개하지 않고 세 가지 핵심 흐름만 보여드려요.",
      coverageCount: available.length,
      coverageLabel: `${available.length}/3개`,
      limited,
      conflict,
      signalAction: compact(safeQuant.current?.action) || null,
      signalLabel: canonicalLabel || null,
      entryAllowed: safeQuant.confirmation?.entry_allowed === true,
      decisionLevels: responseDecisionLevels(safeDashboard, safeQuant),
      publicReasons,
      warnings: [],
      nextChecks: ["20일·60일 가격 흐름과 수급 변화를 다시 확인하세요."],
    };
  };

  return Object.freeze({
    VERSION,
    PUBLIC_REASON_KEYS,
    buildResponse,
    buildInvestorGuide,
  });
}));
