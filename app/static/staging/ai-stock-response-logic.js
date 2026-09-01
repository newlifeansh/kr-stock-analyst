/*
 * Secret Note — per-stock multi-signal response model
 *
 * The browser adapter only renders this result. Keeping the scoring in a
 * dependency-free module makes the same inputs deterministic in QA and in the
 * promoted dashboard bundle.
 */
(function attachAiStockResponseLogic(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SecretNoteAiStockResponse = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function createAiStockResponseLogic() {
  "use strict";

  const VERSION = "20260901-decision-scenarios-v3";
  const WEIGHTS = Object.freeze({
    chart: 25,
    flow: 25,
    disclosure: 15,
    news: 10,
    research: 15,
    market: 10,
  });
  const METRIC_ORDER = Object.freeze(["chart", "flow", "disclosure", "news", "research", "market"]);
  const POSITIVE_WORDS = Object.freeze([
    "상향", "호조", "개선", "증가", "수주", "흑자", "서프라이즈", "강세",
    "성장", "돌파", "수혜", "상승", "회복", "호재", "매수",
  ]);
  const NEGATIVE_WORDS = Object.freeze([
    "하향", "부진", "감소", "적자", "쇼크", "약세", "하락", "악화",
    "손실", "둔화", "우려", "급락", "악재", "위기", "매도",
  ]);
  const HARD_DISCLOSURE_RISK_TOKENS = Object.freeze([
    "유상증자결정", "전환사채권발행결정", "신주인수권부사채권발행결정",
    "교환사채권발행결정", "회생절차", "파산신청", "감사의견거절",
    "감사범위제한", "상장폐지", "거래정지", "횡령", "배임",
  ]);
  const numberFormatter = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });

  const number = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const round = (value) => Math.round(Number(value) || 0);
  const compact = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const normalize = (value) => compact(value).toLocaleLowerCase("ko-KR").replace(/[^0-9a-z가-힣]/g, "");
  const unique = (items) => Array.from(new Set(items.filter(Boolean)));
  const signed = (value) => `${value > 0 ? "+" : ""}${round(value)}`;
  const withTopic = (value) => {
    const text = compact(value);
    const last = text.charCodeAt(text.length - 1);
    const hasFinalConsonant = last >= 0xac00 && last <= 0xd7a3 && (last - 0xac00) % 28 !== 0;
    return `${text}${hasFinalConsonant ? "은" : "는"}`;
  };
  const compactKrw = (value) => {
    const parsed = number(value);
    if (parsed === null) return "-";
    const sign = parsed > 0 ? "+" : parsed < 0 ? "-" : "";
    const absolute = Math.abs(parsed);
    if (absolute >= 1_000_000_000_000) return `${sign}${(absolute / 1_000_000_000_000).toFixed(1)}조원`;
    if (absolute >= 100_000_000) return `${sign}${numberFormatter.format(absolute / 100_000_000)}억원`;
    if (absolute >= 10_000) return `${sign}${numberFormatter.format(absolute / 10_000)}만원`;
    return `${sign}${numberFormatter.format(absolute)}원`;
  };
  const priceText = (value) => {
    const parsed = number(value);
    return parsed === null || parsed <= 0 ? "가격 자료 부족" : `${numberFormatter.format(parsed)}원`;
  };
  const percentText = (value) => {
    const parsed = number(value);
    if (parsed === null) return "수익률 계산 전";
    return `${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}%`;
  };
  const roundTradePrice = (value) => {
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
  const newestAsOf = (...values) => values
    .flat(Infinity)
    .filter(Boolean)
    .map((value) => ({ value, timestamp: Date.parse(String(value)) }))
    .filter((item) => Number.isFinite(item.timestamp))
    .sort((left, right) => right.timestamp - left.timestamp)[0]?.value || null;
  const keywordScore = (value) => {
    const text = compact(value);
    return POSITIVE_WORDS.reduce((score, token) => score + Number(text.includes(token)), 0)
      - NEGATIVE_WORDS.reduce((score, token) => score + Number(text.includes(token)), 0);
  };
  const withinDays = (value, anchorValue, days) => {
    const timestamp = Date.parse(String(value || ""));
    const anchor = Date.parse(String(anchorValue || ""));
    if (!Number.isFinite(timestamp) || !Number.isFinite(anchor)) return false;
    const age = anchor - timestamp;
    return age >= 0 && age <= days * 24 * 60 * 60 * 1000;
  };
  const scoreForState = (state) => {
    const normalized = normalize(state);
    if (["supportive", "positive", "호재", "우호"].some((token) => normalized.includes(normalize(token)))) return 50;
    if (["caution", "negative", "악재", "주의"].some((token) => normalized.includes(normalize(token)))) return -50;
    return 0;
  };
  const statusForScore = (score, { available = true, hardRisk = false } = {}) => {
    if (!available) return "확인 중";
    if (hardRisk) return "위험 감지";
    if (score >= 25) return "우호";
    if (score <= -25) return "주의";
    return "중립";
  };
  const toneForScore = (score, { available = true, hardRisk = false } = {}) => {
    if (!available) return "limited";
    if (hardRisk || score <= -25) return "negative";
    if (score >= 25) return "positive";
    return "neutral";
  };
  const evidenceItems = (quant) => Array.isArray(quant?.confirmation?.evidence)
    ? quant.confirmation.evidence.filter((item) => item && typeof item === "object")
    : [];
  const findEvidence = (quant, keys) => {
    const candidates = evidenceItems(quant);
    for (const key of keys) {
      const match = candidates.find((item) => String(item.key || "") === key);
      if (match) return match;
    }
    return null;
  };
  const baseMetric = ({ key, label, score = null, value = "자료 확인 중", evidence, source, asOf,
    available = false, confidence = 0, hardRisk = false, relevance = "direct" }) => ({
    key,
    label,
    weight: WEIGHTS[key],
    score: available && number(score) !== null ? clamp(number(score), -100, 100) : null,
    value,
    evidence: compact(evidence) || "연결된 근거를 확인하고 있습니다.",
    source: compact(source) || "자료 확인 중",
    asOf: asOf || null,
    available: Boolean(available),
    confidence: clamp(number(confidence) || 0, 0, 1),
    hardRisk: Boolean(hardRisk),
    relevance,
    status: statusForScore(number(score) || 0, { available, hardRisk }),
    tone: toneForScore(number(score) || 0, { available, hardRisk }),
  });

  const chartMetric = (dashboard, quant) => {
    const chart = dashboard?.chart_analysis;
    const rawScore = number(chart?.score);
    if (rawScore === null || compact(chart?.stance).includes("데이터 부족")) {
      const currentScore = number(quant?.current?.score);
      if (currentScore === null) {
        return baseMetric({ key: "chart", label: "차트 점수" });
      }
      const normalizedScore = clamp((currentScore - 50) * 2, -100, 100);
      return baseMetric({
        key: "chart",
        label: "차트 점수",
        score: normalizedScore,
        value: `${round(currentScore)}점`,
        evidence: compact(quant?.current?.reasons?.[0]) || compact(quant?.current?.next_confirmation),
        source: compact(quant?.source) || "확정 일봉 기반 정량 시그널",
        asOf: quant?.current?.as_of || quant?.price_through || quant?.as_of,
        available: true,
        confidence: quant?.data_state === "ready" ? 0.95 : 0.72,
      });
    }
    const normalizedScore = clamp((rawScore - 50) * 2, -100, 100);
    const detail = unique([
      chart?.trend,
      chart?.setup,
      quant?.current?.label,
      normalizedScore >= 0 ? chart?.signals?.[0] : chart?.risks?.[0],
    ]).join(" · ");
    return baseMetric({
      key: "chart",
      label: "차트 점수",
      score: normalizedScore,
      value: `${round(rawScore)}점`,
      evidence: detail,
      source: "확정 일봉·이동평균·거래량·ATR",
      asOf: dashboard?.quote?.trade_date || dashboard?.as_of,
      available: true,
      confidence: dashboard?.coverage?.price === false ? 0.7 : 0.96,
    });
  };

  const flowMetric = (dashboard, quant) => {
    const connected = findEvidence(quant, ["flow"]);
    if (connected && connected.available !== false) {
      const score = number(connected.score) ?? scoreForState(connected.state);
      return baseMetric({
        key: "flow",
        label: "수급",
        score,
        value: `${signed(score)}점`,
        evidence: connected.summary,
        source: connected.source || "투자자별 매매동향",
        asOf: connected.as_of || quant?.as_of,
        available: true,
        confidence: 0.94,
      });
    }
    const flow = dashboard?.flows || {};
    const foreignIntensity = number(flow.foreign_intensity);
    const institutionIntensity = number(flow.institution_intensity);
    const available = foreignIntensity !== null || institutionIntensity !== null;
    if (!available) return baseMetric({ key: "flow", label: "수급" });
    const score = clamp(((foreignIntensity || 0) + (institutionIntensity || 0)) * 10, -100, 100);
    return baseMetric({
      key: "flow",
      label: "수급",
      score,
      value: `${signed(score)}점`,
      evidence: `20일 외국인 ${compactKrw(flow.foreign_net_buy_20d)} · 기관 ${compactKrw(flow.institution_net_buy_20d)}`,
      source: "네이버금융 투자자별 매매동향",
      asOf: dashboard?.as_of,
      available: true,
      confidence: 0.82,
    });
  };

  const disclosureMetric = (homeContext, quant) => {
    const vetoes = Array.isArray(quant?.confirmation?.vetoes)
      ? quant.confirmation.vetoes.map(compact).filter(Boolean)
      : [];
    const connected = findEvidence(quant, ["disclosure_risk", "disclosure"]);
    const entryReason = compact(quant?.current?.entry_confirmation?.reason);
    const anchorAsOf = quant?.as_of || homeContext?.as_of;
    const disclosures = Array.isArray(homeContext?.disclosures) ? homeContext.disclosures : [];
    const names = disclosures.map((item) => compact(item?.report_name || item?.title)).filter(Boolean);
    const hardRiskDisclosure = disclosures.find((item) => {
      const name = compact(item?.report_name || item?.title);
      const recent = withinDays(item?.published_at, anchorAsOf, 14);
      return recent && HARD_DISCLOSURE_RISK_TOKENS.some(
        (token) => normalize(name).includes(normalize(token)),
      );
    });
    const hardRiskName = compact(hardRiskDisclosure?.report_name || hardRiskDisclosure?.title);
    const connectedNamesHardRisk = Boolean(
      connected
      && withinDays(connected.as_of, anchorAsOf, 14)
      && HARD_DISCLOSURE_RISK_TOKENS.some(
        (token) => normalize(connected.summary).includes(normalize(token)),
      )
    );
    const connectedHardRisk = Boolean(
      vetoes.some((item) => /공시|증자|사채|상장폐지|거래정지|횡령|배임/.test(item))
      || (/신규매수 차단|blocked/.test(entryReason) && /공시|증자|사채|상장폐지|거래정지|횡령|배임/.test(entryReason))
      || hardRiskName
      || connectedNamesHardRisk
      || (
        connected?.key === "disclosure_risk"
        && connected.available !== false
        && number(connected.score) !== null
        && number(connected.score) <= -90
      ),
    );
    if (connected && connected.available !== false) {
      const score = connectedHardRisk ? -100 : (number(connected.score) ?? scoreForState(connected.state));
      return baseMetric({
        key: "disclosure",
        label: "공시",
        score,
        value: connectedHardRisk ? "위험 공시" : score < -20 ? "주의 필요" : "차단 없음",
        evidence: vetoes[0] || entryReason || (hardRiskName ? `중대 위험 공시 감지 · ${hardRiskName}` : connected.summary),
        source: connected.source || "OpenDART 공시",
        asOf: connected.as_of || quant?.as_of,
        available: true,
        confidence: 0.98,
        hardRisk: connectedHardRisk,
      });
    }
    if (!disclosures.length) return baseMetric({ key: "disclosure", label: "공시" });
    const lexical = names.reduce((total, name) => total + keywordScore(name), 0);
    const score = hardRiskName ? -100 : clamp(lexical * 20, -80, 80);
    return baseMetric({
      key: "disclosure",
      label: "공시",
      score,
      value: hardRiskName ? "위험 공시" : score < -20 ? "주의 필요" : "차단 없음",
      evidence: hardRiskName ? `중대 위험 공시 감지 · ${hardRiskName}` : `${names.length}건 · 최근 ${names[0]}`,
      source: "OpenDART 공시",
      asOf: disclosures[0]?.published_at || homeContext?.as_of,
      available: true,
      confidence: 0.84,
      hardRisk: Boolean(hardRiskName),
    });
  };

  const newsMetric = (dashboard, homeContext, quant) => {
    const connected = findEvidence(quant, ["news"]);
    if (connected && connected.available !== false) {
      const score = number(connected.score) ?? scoreForState(connected.state);
      return baseMetric({
        key: "news",
        label: "뉴스",
        score,
        value: `${signed(score)}점`,
        evidence: connected.summary,
        source: connected.source || "종목 뉴스",
        asOf: connected.as_of || quant?.as_of,
        available: true,
        confidence: 0.86,
      });
    }
    const sentiment = dashboard?.sentiment;
    const sentimentScore = number(sentiment?.score);
    if (sentimentScore !== null) {
      const latestTitle = compact(sentiment?.latest_items?.[0]?.title);
      return baseMetric({
        key: "news",
        label: "뉴스",
        score: sentimentScore,
        value: `${signed(sentimentScore)}점`,
        evidence: `긍정 ${round(sentiment?.positive_count)} · 부정 ${round(sentiment?.negative_count)} · 중립 ${round(sentiment?.neutral_count)}${latestTitle ? ` · 최근 ${latestTitle}` : ""}`,
        source: "저장 뉴스 + 네이버금융 종목뉴스",
        asOf: sentiment?.latest_items?.[0]?.published_at || dashboard?.as_of,
        available: true,
        confidence: 0.88,
      });
    }
    const items = Array.isArray(homeContext?.news_items) ? homeContext.news_items : [];
    if (!items.length) return baseMetric({ key: "news", label: "뉴스" });
    const scores = items.map((item) => keywordScore(`${item?.title || ""} ${item?.summary || ""}`));
    const positive = scores.filter((score) => score > 0).length;
    const negative = scores.filter((score) => score < 0).length;
    const score = clamp(((positive - negative) / scores.length) * 100, -100, 100);
    return baseMetric({
      key: "news",
      label: "뉴스",
      score,
      value: `${signed(score)}점`,
      evidence: `긍정 ${positive} · 부정 ${negative} · 중립 ${scores.length - positive - negative} · 최근 ${compact(items[0]?.title)}`,
      source: "네이버금융 종목뉴스",
      asOf: items[0]?.published_at || homeContext?.as_of,
      available: true,
      confidence: 0.76,
    });
  };

  const researchMetric = (dashboard, homeContext, quant) => {
    const connected = findEvidence(quant, ["research", "earnings"]);
    if (connected && connected.available !== false) {
      const score = number(connected.score) ?? scoreForState(connected.state);
      return baseMetric({
        key: "research",
        label: "증권사 리포트",
        score,
        value: `${signed(score)}점`,
        evidence: connected.summary,
        source: connected.source || "증권사 발간 리포트",
        asOf: connected.as_of || quant?.as_of,
        available: true,
        confidence: 0.92,
      });
    }
    const revisions = dashboard?.revisions || {};
    const reports = Array.isArray(homeContext?.research_reports) && homeContext.research_reports.length
      ? homeContext.research_reports
      : Array.isArray(revisions.recent_reports)
        ? revisions.recent_reports
        : [];
    const reportCount = number(revisions.report_count_90d) ?? reports.length;
    if (!reports.length && !reportCount) {
      return baseMetric({ key: "research", label: "증권사 리포트" });
    }
    const latest = reports[0] || {};
    const opinion = compact(latest.opinion || revisions.latest_opinion);
    const title = compact(latest.title);
    const revisionUp = number(revisions.target_up_count) || 0;
    const revisionDown = number(revisions.target_down_count) || 0;
    const targetPrice = number(latest.target_price ?? revisions.latest_target_price);
    let score = clamp((revisionUp - revisionDown) * 25 + keywordScore(`${opinion} ${title}`) * 12, -100, 100);
    if (/매수|buy|outperform/i.test(opinion)) score = clamp(score + 20, -100, 100);
    if (/매도|sell|reduce/i.test(opinion)) score = clamp(score - 30, -100, 100);
    const details = unique([
      `${round(reportCount)}건`,
      compact(latest.broker_name),
      opinion,
      targetPrice ? `목표가 ${numberFormatter.format(targetPrice)}원` : "",
      title,
    ]).join(" · ");
    return baseMetric({
      key: "research",
      label: "증권사 리포트",
      score,
      value: targetPrice ? `목표가 ${numberFormatter.format(targetPrice)}원` : `${round(reportCount)}건`,
      evidence: details || "최근 증권사 리포트의 의견과 목표가 변화를 확인했어요.",
      source: "증권사 발간 리포트",
      asOf: latest.published_at || revisions.latest_report_at || homeContext?.as_of,
      available: true,
      confidence: clamp(0.58 + Math.min(round(reportCount), 4) * 0.08, 0, 0.9),
    });
  };

  const marketDirection = (value) => {
    const normalized = normalize(value);
    if (normalized.includes("호재")) return 1;
    if (normalized.includes("악재")) return -1;
    return 0;
  };
  const stockTerms = (dashboard, quant) => unique([
    quant?.name,
    dashboard?.name,
    quant?.sector,
    quant?.industry,
    quant?.investment_sector_label,
    dashboard?.company_profile?.sector,
    dashboard?.company_profile?.industry,
  ].map(normalize).filter((term) => term.length >= 2 && !["기타", "other"].includes(term)));
  const marketMetric = (dashboard, marketImpact, quant, fallbackDetail) => {
    const factors = Array.isArray(marketImpact?.factors)
      ? marketImpact.factors.filter((factor) => factor && factor.direction !== "자료 부족")
      : [];
    if (!factors.length || marketImpact?.data_quality === "자료 부족") {
      return baseMetric({
        key: "market",
        label: "시장 영향",
        evidence: fallbackDetail?.issue,
        source: "시장 영향 자료 확인 중",
      });
    }
    const terms = stockTerms(dashboard, quant);
    const name = normalize(quant?.name || dashboard?.name || fallbackDetail?.name);
    const relevant = factors.filter((factor) => {
      const leaders = Array.isArray(factor.leader_stocks) ? factor.leader_stocks.map(normalize) : [];
      const sectors = Array.isArray(factor.affected_sectors) ? factor.affected_sectors.map(normalize) : [];
      const leaderMatch = leaders.some((leader) => leader && name && (leader.includes(name) || name.includes(leader)));
      const sectorMatch = sectors.some((sector) => sector && terms.some((term) => sector.includes(term) || term.includes(sector)));
      return leaderMatch || sectorMatch;
    });
    const selected = relevant.length ? relevant : factors;
    const totalPercent = selected.reduce((total, factor) => total + Math.max(0, number(factor.percent) || 0), 0);
    const weightedDirection = selected.reduce((total, factor) => {
      const percent = Math.max(0, number(factor.percent) || 0);
      const confidence = clamp(number(factor.confidence) ?? 50, 0, 100);
      return total + (percent * marketDirection(factor.direction) * confidence);
    }, 0);
    const score = totalPercent > 0
      ? clamp(weightedDirection / totalPercent, -100, 100)
      : clamp((number(marketImpact.good_weight) || 0) - (number(marketImpact.bad_weight) || 0), -100, 100);
    const averageConfidence = totalPercent > 0
      ? selected.reduce((total, factor) => total + ((number(factor.percent) || 0) * (number(factor.confidence) || 50)), 0) / totalPercent / 100
      : 0.5;
    const factorSummary = selected
      .slice()
      .sort((left, right) => (number(right.percent) || 0) - (number(left.percent) || 0))
      .slice(0, 2)
      .map((factor) => `${compact(factor.label)} ${compact(factor.direction)} ${round(factor.percent)}%`)
      .join(" · ");
    const relevance = relevant.length ? "direct" : "broad";
    return baseMetric({
      key: "market",
      label: "시장 영향",
      score,
      value: `${signed(score)}점`,
      evidence: relevance === "direct"
        ? `종목·업종 관련 축 · ${factorSummary}`
        : `${compact(marketImpact.summary)}${factorSummary ? ` · ${factorSummary}` : ""}`,
      source: relevance === "direct" ? "시장 5개 축·종목/업종 연관" : "시장 5개 축·광역 영향",
      asOf: marketImpact?.data_as_of || marketImpact?.as_of,
      available: true,
      confidence: clamp(averageConfidence * (relevance === "direct" ? 1 : 0.72), 0, 1),
      relevance,
    });
  };

  const nextChecks = (metrics, dashboard, quant, hardRisk) => {
    const chart = dashboard?.chart_analysis || {};
    const checks = [];
    if (hardRisk) checks.push("공시 원문과 거래 상태를 먼저 확인");
    if (compact(quant?.current?.next_confirmation)) {
      checks.push(`현재 시그널: ${compact(quant.current.next_confirmation)}`);
    }
    if (number(chart.support) !== null) checks.push(`차트 지지 ${numberFormatter.format(number(chart.support))}원 유지 여부`);
    else checks.push("차트 종가와 20일선 방향 재확인");
    const flow = metrics.find((metric) => metric.key === "flow");
    checks.push(flow?.score < 0 ? "외국인·기관 합산 순매수 전환 확인" : "수급 우호 흐름의 연속성 확인");
    const news = metrics.find((metric) => metric.key === "news");
    if (news?.score < 0) checks.push("부정 뉴스의 실적·사업 영향 범위 확인");
    const market = metrics.find((metric) => metric.key === "market");
    if (market?.score < 0) checks.push("관련 시장 위험축의 방향 전환 확인");
    return unique(checks).slice(0, 3);
  };

  const nearestPriceBelow = (currentPrice, candidates) => {
    const usable = candidates
      .map(number)
      .filter((value) => value !== null && value > 0 && value < currentPrice);
    return usable.length ? Math.max(...usable) : null;
  };

  const nearestPriceAbove = (currentPrice, candidates) => {
    const usable = candidates
      .map(number)
      .filter((value) => value !== null && value > currentPrice);
    return usable.length ? Math.min(...usable) : null;
  };

  const nearestPriceBelowWithin = (
    currentPrice,
    candidates,
    { minPercent = 0, maxPercent = 12 } = {},
  ) => {
    const usable = candidates
      .map(number)
      .filter((value) => {
        if (value === null || value <= 0 || value >= currentPrice) return false;
        const distance = (currentPrice - value) / currentPrice * 100;
        return distance >= minPercent && distance <= maxPercent;
      });
    return usable.length ? Math.max(...usable) : null;
  };

  const nearestPriceAboveWithin = (
    currentPrice,
    candidates,
    { minPercent = 0, maxPercent = 12 } = {},
  ) => {
    const usable = candidates
      .map(number)
      .filter((value) => {
        if (value === null || value <= currentPrice) return false;
        const distance = (value - currentPrice) / currentPrice * 100;
        return distance >= minPercent && distance <= maxPercent;
      });
    return usable.length ? Math.min(...usable) : null;
  };

  const responseDecisionLevels = (dashboard, quant) => {
    const chart = dashboard?.chart_analysis || {};
    const current = quant?.current || {};
    const currentPrice = number(dashboard?.quote?.price) ?? number(current.price);
    if (currentPrice === null || currentPrice <= 0) {
      return {
        currentPrice: null,
        changeRate: number(dashboard?.quote?.change_rate),
        quoteAsOf: dashboard?.quote?.as_of || dashboard?.quote?.trade_date || dashboard?.as_of || null,
        marketSession: compact(dashboard?.quote?.market_session),
        quoteIsLive: dashboard?.quote?.is_live === true,
        watchLow: null,
        watchHigh: null,
        buyTrigger: null,
        riskLine: null,
        firstSell: null,
        support: number(chart.support),
        resistance: number(chart.resistance),
      };
    }
    const atrPercent = clamp(number(chart.atr_percent) ?? 3, 1, 8);
    const support = number(chart.support);
    const resistance = number(chart.resistance);
    const movingAverages = chart.moving_averages || {};
    const movingAveragePrices = [
      movingAverages.ma5,
      movingAverages.ma20,
      movingAverages.ma60,
      movingAverages.ma120,
    ].map(number).filter((value) => value !== null);
    const recentPatterns = (Array.isArray(chart.patterns) ? chart.patterns : [])
      .filter((pattern) => pattern?.is_recent !== false);
    const patternTriggers = recentPatterns.flatMap((pattern) => [
      pattern?.trigger,
      pattern?.boundaries?.upper?.end_price,
      pattern?.boundaries?.lower?.end_price,
    ]);
    const patternTargets = recentPatterns.flatMap((pattern) => [
      pattern?.target,
      pattern?.invalidation,
      pattern?.boundaries?.upper?.end_price,
      pattern?.boundaries?.lower?.end_price,
    ]);
    const signalLevels = Array.isArray(current.levels) ? current.levels : [];
    const signalPrice = (...keys) => number(signalLevels.find(
      (level) => keys.includes(compact(level?.key)),
    )?.price);
    const signalContextActive = compact(current.action) !== "exited";
    const stopCandidate = nearestPriceBelowWithin(currentPrice, [
      signalContextActive ? current.stop_reference : null,
      signalContextActive ? signalPrice("stop", "full_exit", "risk") : null,
      ...movingAveragePrices,
      ...patternTargets,
      support,
    ], { minPercent: 0.5, maxPercent: 12 });
    const riskLine = roundTradePrice(
      stopCandidate ?? currentPrice * (1 - clamp(atrPercent * 0.55, 2, 3.5) / 100),
    );
    const watchHigh = roundTradePrice(currentPrice * (1 - clamp(atrPercent * 0.1, 0.2, 0.6) / 100));
    const fallbackWatchLow = currentPrice * (1 - clamp(atrPercent * 0.45, 1, 2.2) / 100);
    const nearbySupport = nearestPriceBelowWithin(currentPrice, [
      ...movingAveragePrices,
      ...patternTargets,
      support,
    ], { minPercent: 0.5, maxPercent: 8 });
    const watchLow = roundTradePrice(Math.max(fallbackWatchLow, nearbySupport || 0));
    const buyTrigger = roundTradePrice(
      nearestPriceAboveWithin(currentPrice, [
        current.entry_confirmation?.price,
        signalPrice("entry", "breakout"),
        ...patternTriggers,
        ...movingAveragePrices,
        resistance,
      ], { minPercent: 0.7, maxPercent: 12 })
        ?? currentPrice * (1 + clamp(atrPercent * 0.35, 1.2, 2.5) / 100),
    );
    const firstSell = roundTradePrice(
      nearestPriceAboveWithin(currentPrice, [
        signalContextActive ? current.partial_exit_reference : null,
        signalContextActive ? current.target_sell_price : null,
        signalContextActive ? signalPrice("partial_exit", "target") : null,
        ...movingAveragePrices,
        ...patternTargets,
        resistance,
      ], { minPercent: 2.5, maxPercent: 20 })
        ?? currentPrice * (1 + clamp(atrPercent * 0.8, 3, 5.5) / 100),
    );
    return {
      currentPrice: roundTradePrice(currentPrice),
      changeRate: number(dashboard?.quote?.change_rate),
      quoteAsOf: dashboard?.quote?.as_of || dashboard?.quote?.trade_date || dashboard?.as_of || null,
      marketSession: compact(dashboard?.quote?.market_session),
      quoteIsLive: dashboard?.quote?.is_live === true,
      watchLow,
      watchHigh,
      buyTrigger,
      riskLine,
      firstSell,
      support: roundTradePrice(support),
      resistance: roundTradePrice(resistance),
      strategyEntryPrice: roundTradePrice(current.entry_price),
      lockedProfitReference: roundTradePrice(current.locked_profit_reference),
      signalAction: compact(current.action),
    };
  };

  const metricDirectionText = (metric) => {
    if (!metric || metric.available === false) return "자료 부족";
    if (metric.hardRisk) return "중대 위험";
    if (number(metric.score) >= 25) return "긍정";
    if (number(metric.score) <= -25) return "주의";
    return "뚜렷한 방향 없음";
  };

  const investorReason = (result) => {
    const metrics = new Map((result?.metrics || []).map((metric) => [metric.key, metric]));
    return [
      ["chart", "가격 흐름"],
      ["flow", "외국인·기관 매매"],
      ["news", "최근 뉴스"],
      ["research", "증권사 리포트"],
    ].map(([key, label]) => {
      const direction = metricDirectionText(metrics.get(key));
      if (direction === "자료 부족") return `${withTopic(label)} 자료가 부족해요.`;
      if (direction === "뚜렷한 방향 없음") return `${withTopic(label)} 방향이 뚜렷하지 않아요.`;
      return `${withTopic(label)} ${direction} 신호예요.`;
    }).join(" ");
  };

  const guideRow = (key, label, status, value, evidence, tone = "neutral") => ({
    key,
    label,
    status,
    value,
    evidence,
    tone,
  });

  const decisionStep = (key, label, status, value, evidence, tone = "neutral") => ({
    key,
    label,
    status,
    value,
    evidence,
    tone,
  });

  const buildInvestorGuide = (result = {}, { investorState = "not_holding", averageBuyPrice = null } = {}) => {
    const state = investorState === "holding" ? "holding" : "not_holding";
    const levels = result.decisionLevels || {};
    const currentPrice = number(levels.currentPrice);
    const averagePrice = state === "holding" ? number(averageBuyPrice) : null;
    const returnRate = currentPrice !== null && averagePrice !== null && averagePrice > 0
      ? (currentPrice / averagePrice - 1) * 100
      : null;
    const reason = investorReason(result);
    const buyConditionReady = !result.hardRisk
      && !result.limited
      && !result.conflict
      && number(result.score) >= 10
      && result.entryAllowed === true
      && ["entry_pending", "entered"].includes(compact(result.signalAction));
    const metricMap = new Map((result.metrics || []).map((metric) => [metric.key, metric]));
    const commonNext = unique([
      number(metricMap.get("flow")?.score) < 0
        ? "외국인과 기관이 판 금액보다 산 금액이 많아지는지"
        : "외국인과 기관의 매수가 이어지는지",
      number(metricMap.get("news")?.score) < 0
        ? "부정 뉴스가 실적과 사업에 실제로 영향을 주는지"
        : "최근 뉴스의 긍정 흐름이 실적 변화로 이어지는지",
      "중요한 회사 공시가 새로 나오는지",
      "증권사 목표가와 투자의견이 바뀌는지",
    ]);
    if (state === "not_holding") {
      const headline = buyConditionReady
        ? "매수 조건은 확인됐지만 가격이 안정되는지 먼저 볼 때예요"
        : "현재는 매수 관망이 필요해요";
      const summary = buyConditionReady
        ? "신호가 기준을 통과했어도 한 번에 따라가기보다 가격과 거래 흐름이 함께 유지되는지 확인해요."
        : "외국인·기관 매매, 뉴스, 가격 흐름, 증권사 리포트가 같은 방향으로 모이지 않아 새로 사는 판단은 잠시 미뤄 두는 구간이에요.";
      return {
        state,
        positionMode: buyConditionReady ? "buy_conditions_ready" : "watching",
        headline,
        summary,
        reason,
        direction: buyConditionReady ? "매수 조건 확인" : "매수 관망",
        directionGuide: buyConditionReady ? "가격과 거래 흐름이 함께 유지되는지 보세요" : "신호가 같은 방향으로 모이는지 기다려요",
        currentPrice,
        averageBuyPrice: null,
        returnRate: null,
        rows: [
          guideRow(
            "watch_zone",
            buyConditionReady ? "가격이 내려올 때 볼 구간" : "눌림목 확인 구간",
            buyConditionReady ? "1차 분할 매수 검토" : "하락 멈춤 확인",
            levels.watchLow && levels.watchHigh
              ? `${numberFormatter.format(levels.watchLow)}~${numberFormatter.format(levels.watchHigh)}원`
              : "가격 자료 부족",
            buyConditionReady
              ? "가격이 이 구간까지 내려온 뒤 더 떨어지지 않고, 실제 거래 규모와 외국인·기관 매매가 좋아지면 1차 분할 매수를 검토해요."
              : "가격이 이 구간까지 내려온 뒤 더 떨어지지 않고 반등하는지 보는 눌림목 구간이에요. 가격에 닿았다는 이유만으로 바로 사지는 않아요.",
            buyConditionReady ? "positive" : "neutral",
          ),
          guideRow(
            "buy_trigger",
            "상승 흐름 확인선",
            "매수가 아님",
            priceText(levels.buyTrigger),
            "현재가보다 높은 이 가격은 바로 사는 매수가가 아니에요. 이 가격 위에서 장을 마치고 실제 거래 규모와 외국인·기관 매매가 함께 좋아지면 상승 흐름이 다시 확인된 것으로 봐요.",
            "positive",
          ),
          guideRow(
            "risk_line",
            "관망을 이어갈 기준",
            "주의",
            priceText(levels.riskLine),
            "이 가격 아래에서는 가격 흐름이 더 약해질 수 있어 신규 매수 판단을 계속 미뤄요.",
            "negative",
          ),
        ],
        decisionPlan: [
          decisionStep(
            "pullback",
            "가격이 내려올 때",
            "1차 분할 매수 검토",
            levels.watchLow && levels.watchHigh
              ? `${numberFormatter.format(levels.watchLow)}~${numberFormatter.format(levels.watchHigh)}원`
              : "가격 자료 부족",
            "이 구간에서 하락이 멈추고 반등하면서 외국인·기관의 매도가 줄면, 적은 수량부터 나눠 살지 검토해요.",
            "neutral",
          ),
          decisionStep(
            "breakout",
            "가격이 올라갈 때",
            "매수가 아님",
            priceText(levels.buyTrigger),
            "이 가격은 상승 흐름 확인선이에요. 거래가 늘며 이 가격 위에서 장을 마쳐도 바로 따라 사기보다, 다시 이 가격을 지키는지 확인한 뒤 분할 매수를 검토해요.",
            "positive",
          ),
          decisionStep(
            "wait",
            "계속 기다릴 때",
            "관망 유지",
            priceText(levels.riskLine),
            "이 가격 아래에서 장을 마치거나 외국인·기관의 매도가 더 늘면 신규 매수는 계속 미뤄요.",
            "negative",
          ),
        ],
        nextChecks: unique([
          number(levels.buyTrigger) !== null
            ? `${priceText(levels.buyTrigger)} 위에서 장을 마친 뒤 다시 그 가격을 지키는지`
            : null,
          ...commonNext,
        ]).slice(0, 5),
      };
    }

    if (returnRate === null) {
      return {
        state,
        positionMode: "holding_unknown",
        headline: "평균 매수가를 입력하면 보유 대응을 손익에 맞춰 볼 수 있어요",
        summary: "현재가만으로는 수익인지 손실인지 알 수 없어 일반적인 보유·위험 기준을 먼저 보여드려요.",
        reason,
        direction: "매수가 입력 필요",
        directionGuide: "내 평균 매수가를 입력해 주세요",
        currentPrice,
        averageBuyPrice: null,
        returnRate: null,
        rows: [
          guideRow("current_price", "현재가", "기준 가격", priceText(currentPrice), "평균 매수가와 비교하면 현재 수익·손실 구간을 계산할 수 있어요."),
          guideRow("risk_line", "손실 제한 참고선", "주의", priceText(levels.riskLine), "가격이 이 기준 아래로 내려가면서 외국인과 기관의 매도까지 늘어나는지 확인해요.", "negative"),
          guideRow("first_sell", "1차 분할 매도 참고선", "수익 관리", priceText(levels.firstSell), "수익권에 도달하면 일부 이익을 나눠 지킬지 검토하는 참고 가격이에요.", "positive"),
        ],
        decisionPlan: [
          decisionStep(
            "enter_average",
            "먼저 할 일",
            "평균 매수가 입력",
            "내 매수가 확인",
            "내 평균 매수가를 입력하면 현재 수익인지 손실인지 계산해 상황에 맞는 대응 기준을 보여드려요.",
            "neutral",
          ),
          decisionStep(
            "unknown_down",
            "가격이 내려가면",
            "위험 기준 확인",
            priceText(levels.riskLine),
            "이 가격 아래에서 장을 마치고 외국인·기관 매도도 늘면 보유 수량을 줄일지 검토해요.",
            "negative",
          ),
          decisionStep(
            "unknown_up",
            "가격이 올라가면",
            "일부 매도 검토",
            priceText(levels.firstSell),
            "평균 매수가를 입력한 뒤 실제 수익권이라면 이 가격 부근에서 일부 이익을 지킬지 검토해요.",
            "positive",
          ),
        ],
        nextChecks: unique([
          "내 평균 매수가를 입력해 현재 수익·손실 구간을 확인하기",
          ...commonNext,
        ]).slice(0, 5),
      };
    }

    const profit = returnRate > 0.5;
    const loss = returnRate < -0.5;
    const protectCandidate = nearestPriceBelow(currentPrice, [
      levels.lockedProfitReference,
      profit ? averagePrice : null,
      levels.riskLine,
    ]);
    const protectLine = roundTradePrice(protectCandidate ?? levels.riskLine);
    if (profit) {
      return {
        state,
        positionMode: "holding_profit",
        headline: "현재 수익권이라면 분할 매도로 이익을 지킬 구간을 볼 때예요",
        summary: "한 번에 모두 정하기보다 1차 매도 참고 가격과 이익 보호 기준을 나눠 확인해요.",
        reason,
        direction: "수익 관리",
        directionGuide: "분할 매도와 이익 보호 기준을 함께 봐요",
        currentPrice,
        averageBuyPrice: averagePrice,
        returnRate,
        rows: [
          guideRow("return", "내 수익률", "수익권", percentText(returnRate), `평균 매수가 ${priceText(averagePrice)}과 현재가 ${priceText(currentPrice)}을 비교했어요.`, "positive"),
          guideRow("first_sell", "1차 분할 매도 참고선", "수익 관리", priceText(levels.firstSell), "이 가격 부근에서 일부 이익을 먼저 확보할지 검토해요.", "positive"),
          guideRow("protect", "이익 보호 기준", "주의", priceText(protectLine), "가격이 이 기준 아래로 밀리고 외국인과 기관의 매도도 늘어나면 남은 보유분을 다시 점검해요.", "negative"),
        ],
        decisionPlan: [
          decisionStep(
            "take_profit",
            "가격이 더 오르면",
            "일부 매도 검토",
            priceText(levels.firstSell),
            "이 가격 부근에서는 전량을 한 번에 팔기보다 보유 수량 일부를 나눠 팔아 이익을 지킬지 검토해요.",
            "positive",
          ),
          decisionStep(
            "protect_profit",
            "가격이 다시 내려오면",
            "보유 기준 재점검",
            priceText(protectLine),
            "이 가격 아래에서 장을 마치고 외국인·기관의 매도도 늘면 남은 보유 수량을 줄일지 검토해요.",
            "negative",
          ),
          decisionStep(
            "keep_holding",
            "계속 보유하려면",
            "흐름 유지 확인",
            `${priceText(protectLine)} 위 유지`,
            "가격이 이익 보호 기준 위를 지키고 외국인·기관 매매와 최근 뉴스가 나빠지지 않으면 남은 수량의 보유 기준을 유지해요.",
            "neutral",
          ),
        ],
        nextChecks: unique([
          number(levels.firstSell) !== null
            ? `${priceText(levels.firstSell)} 부근에서 일부 이익을 지킬지`
            : null,
          number(protectLine) !== null
            ? `${priceText(protectLine)} 아래로 밀리는지`
            : null,
          ...commonNext,
        ]).slice(0, 5),
      };
    }
    if (loss) {
      return {
        state,
        positionMode: "holding_loss",
        headline: "현재 손실권이라면 가격별 손실 제한 기준을 먼저 세울 때예요",
        summary: "평균 매수가로 바로 돌아오기를 기다리기보다 약세가 이어지는 가격과 회복을 확인할 가격을 나눠 봐요.",
        reason,
        direction: "손실 관리",
        directionGuide: "손실 제한선과 회복 확인선을 나눠 봐요",
        currentPrice,
        averageBuyPrice: averagePrice,
        returnRate,
        rows: [
          guideRow("return", "내 수익률", "손실권", percentText(returnRate), `평균 매수가 ${priceText(averagePrice)}과 현재가 ${priceText(currentPrice)}을 비교했어요.`, "negative"),
          guideRow("risk_line", "손실 제한 참고선", "주의", priceText(levels.riskLine), "이 가격 아래에서 장을 마치고 외국인과 기관의 매도도 늘어나면 보유 수량을 줄일지 점검해요.", "negative"),
          guideRow("recovery", "회복 확인 가격", "조건 확인", priceText(levels.buyTrigger), "이 가격 위로 회복하면서 실제 거래 규모와 외국인·기관 매매가 좋아지는지 확인해요.", "positive"),
        ],
        decisionPlan: [
          decisionStep(
            "limit_loss",
            "가격이 더 내려가면",
            "손실 제한 검토",
            priceText(levels.riskLine),
            "이 가격 아래에서 장을 마치고 외국인·기관 매도도 늘면 보유 수량을 줄여 손실을 제한할지 검토해요.",
            "negative",
          ),
          decisionStep(
            "recovery",
            "가격이 회복하면",
            "회복 여부 확인",
            priceText(levels.buyTrigger),
            "이 가격 위로 올라온 뒤 다시 밀리지 않고 실제 거래 규모와 외국인·기관 매매가 좋아지는지 확인해요.",
            "positive",
          ),
          decisionStep(
            "hold_loss",
            "계속 보유하려면",
            "조건 동시 확인",
            "가격·매매 함께 확인",
            "가격만 반등하는 경우보다 외국인·기관 매도 감소와 부정 뉴스 완화가 함께 나타나는지 확인해요.",
            "neutral",
          ),
        ],
        nextChecks: unique([
          number(levels.riskLine) !== null
            ? `${priceText(levels.riskLine)} 아래에서 장을 마치는지`
            : null,
          number(levels.buyTrigger) !== null
            ? `${priceText(levels.buyTrigger)} 위로 회복하는지`
            : null,
          ...commonNext,
        ]).slice(0, 5),
      };
    }
    return {
      state,
      positionMode: "holding_flat",
      headline: "현재는 본전권이라 보유 기준과 위험선을 함께 확인할 때예요",
      summary: "작은 등락보다 다음 방향이 정해지는 가격과 외국인·기관 매매 변화를 먼저 봐요.",
      reason,
      direction: "보유 기준 확인",
      directionGuide: "위험선과 수익 관리 가격을 함께 봐요",
      currentPrice,
      averageBuyPrice: averagePrice,
      returnRate,
      rows: [
        guideRow("return", "내 수익률", "본전권", percentText(returnRate), `평균 매수가 ${priceText(averagePrice)}과 현재가 ${priceText(currentPrice)}을 비교했어요.`),
        guideRow("risk_line", "위험 관리 기준", "주의", priceText(levels.riskLine), "이 가격 아래로 밀리면 보유 기준을 다시 점검해요.", "negative"),
        guideRow("first_sell", "수익 관리 참고선", "조건 확인", priceText(levels.firstSell), "이 가격에 가까워지면 분할 매도로 이익을 지킬지 검토해요.", "positive"),
      ],
      decisionPlan: [
        decisionStep(
          "flat_down",
          "가격이 내려가면",
          "보유 기준 재점검",
          priceText(levels.riskLine),
          "이 가격 아래에서 장을 마치고 외국인·기관 매도도 늘면 보유 수량을 줄일지 검토해요.",
          "negative",
        ),
        decisionStep(
          "flat_up",
          "가격이 올라가면",
          "일부 매도 검토",
          priceText(levels.firstSell),
          "이 가격에 가까워지며 수익권으로 바뀌면 일부 이익을 먼저 지킬지 검토해요.",
          "positive",
        ),
        decisionStep(
          "flat_hold",
          "계속 보유하려면",
          "매매 흐름 확인",
          "가격·매매 함께 확인",
          "위험 기준 위를 지키면서 외국인·기관 매도가 늘지 않는지 함께 확인해요.",
          "neutral",
        ),
      ],
      nextChecks: unique([
        number(levels.riskLine) !== null
          ? `${priceText(levels.riskLine)} 아래로 밀리는지`
          : null,
        number(levels.firstSell) !== null
          ? `${priceText(levels.firstSell)} 부근에서 수익 관리가 필요한지`
          : null,
        ...commonNext,
      ]).slice(0, 5),
    };
  };

  const buildResponse = ({ code = "", fallbackDetail = {}, quant = null, dashboard = null,
    homeContext = null, marketImpact = null } = {}) => {
    const metrics = [
      chartMetric(dashboard, quant),
      flowMetric(dashboard, quant),
      disclosureMetric(homeContext, quant),
      newsMetric(dashboard, homeContext, quant),
      researchMetric(dashboard, homeContext, quant),
      marketMetric(dashboard, marketImpact, quant, fallbackDetail),
    ].sort((left, right) => METRIC_ORDER.indexOf(left.key) - METRIC_ORDER.indexOf(right.key));
    const available = metrics.filter((metric) => metric.available && number(metric.score) !== null);
    const effectiveWeight = available.reduce((total, metric) => total + metric.weight, 0);
    const weightedScore = effectiveWeight
      ? available.reduce((total, metric) => total + (metric.score * metric.weight), 0) / effectiveWeight
      : 0;
    const quality = effectiveWeight
      ? available.reduce((total, metric) => total + (metric.confidence * metric.weight), 0) / effectiveWeight * 100
      : 0;
    const absoluteContribution = available.reduce(
      (total, metric) => total + Math.abs(metric.score * metric.weight),
      0,
    );
    const signedContribution = available.reduce(
      (total, metric) => total + (metric.score * metric.weight),
      0,
    );
    const agreement = absoluteContribution ? Math.abs(signedContribution) / absoluteContribution * 100 : 50;
    const positiveMetrics = available.filter((metric) => metric.score >= 25);
    const negativeMetrics = available.filter((metric) => metric.score <= -25);
    const conflict = positiveMetrics.length > 0 && negativeMetrics.length > 0;
    const hardRisk = metrics.some((metric) => metric.hardRisk);
    const limited = available.length < 3 || effectiveWeight < 60;
    const quantAction = compact(quant?.current?.action);
    const quantLabel = compact(quant?.current?.label);
    const quantNext = compact(quant?.current?.next_confirmation);
    let confidence = round((effectiveWeight * 0.45) + (quality * 0.4) + (agreement * 0.15));
    if (limited) confidence = Math.min(confidence, 55);
    if (conflict) confidence = Math.min(confidence, 72);
    confidence = clamp(confidence, 0, 95);

    let stance = "중립 관찰";
    let tone = "neutral";
    let action = "방향이 모일 때까지 비중 확대보다 차트와 수급의 다음 확인 신호를 기다리세요.";
    if (hardRisk) {
      stance = "신규 접근 보류";
      tone = "negative";
      action = "점수보다 중대 공시 확인이 우선입니다. 원문과 거래 상태를 확인할 때까지 신규 접근을 보류하세요.";
    } else if (quantAction === "full_exit_pending") {
      stance = "매도 신호 우선";
      tone = "negative";
      action = quantNext || "현재 시그널의 전량 매도 조건과 다음 거래일 체결 기준을 먼저 확인하세요.";
    } else if (quantAction === "partial_exit_pending") {
      stance = "수익 관리 우선";
      tone = "mixed";
      action = quantNext || "현재 시그널의 단계별 수익확정 조건을 먼저 확인하세요.";
    } else if (quantAction === "exited") {
      stance = "재진입 유예";
      tone = "negative";
      action = quantNext || "전량 매도 후 새 진입 조건이 다시 완성될 때까지 기다리세요.";
    } else if (limited) {
      stance = "정보 확인 우선";
      tone = "limited";
      action = "차트·수급·공시 중 빠진 자료를 먼저 채운 뒤 대응을 결정하세요.";
    } else if (conflict) {
      stance = weightedScore <= -15 ? "보수 관찰" : "혼조 · 확인 우선";
      tone = "mixed";
      action = "우호·주의 신호가 엇갈립니다. 추격하지 말고 차트 방향과 수급이 같은 쪽으로 모이는지 확인하세요.";
    } else if (weightedScore >= 35) {
      stance = "분할 접근 검토";
      tone = "positive";
      action = "우호 신호가 모였습니다. 추격보다 지지선 유지와 수급 동반을 확인하며 분할 접근을 검토하세요.";
    } else if (weightedScore >= 10) {
      stance = "긍정 관찰";
      tone = "positive";
      action = "긍정 우위지만 확정 신호는 아닙니다. 지지선과 외국인·기관 수급이 이어지는지 확인하세요.";
    } else if (weightedScore <= -35) {
      stance = "위험 관리 우선";
      tone = "negative";
      action = "주의 신호가 우세합니다. 신규 접근을 서두르지 말고 지지선과 공시 위험을 우선 점검하세요.";
    } else if (weightedScore <= -10) {
      stance = "보수 대응";
      tone = "negative";
      action = "약한 주의 우위입니다. 반등만 추격하지 말고 수급 전환과 차트 회복을 먼저 확인하세요.";
    }
    if (!hardRisk && !limited && !conflict && quantAction === "entry_watch" && weightedScore >= 10) {
      stance = "조건 확인 중";
      tone = "neutral";
      action = quantNext || "가격 조건 외 독립 근거가 더 확인될 때까지 예비 상태로 관찰하세요.";
    } else if (!hardRisk && !limited && !conflict && quantAction === "entry_pending" && weightedScore >= 10) {
      stance = "진입 조건 확인";
      tone = "positive";
      action = quantNext || "다음 거래일 시가의 갭 범위와 수급 지속성을 확인하세요.";
    } else if (
      !hardRisk
      && !limited
      && !conflict
      && ["entered", "holding", "partially_exited"].includes(quantAction)
      && weightedScore > -10
    ) {
      stance = quantAction === "partially_exited" ? "수익확정 후 보유 관리" : "보유 관리";
      tone = weightedScore >= 10 ? "positive" : "neutral";
      action = quantNext || "보유 신호의 위험선과 다음 수익확정 조건을 함께 확인하세요.";
    }

    const strongestPositive = positiveMetrics.slice().sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0];
    const strongestNegative = negativeMetrics.slice().sort((a, b) => (a.score * a.weight) - (b.score * b.weight))[0];
    const summaryParts = [];
    if (strongestPositive) summaryParts.push(`${withTopic(strongestPositive.label)} 우호`);
    if (strongestNegative) summaryParts.push(`${withTopic(strongestNegative.label)} 주의`);
    if (!summaryParts.length && available.length) summaryParts.push("강한 방향 신호는 아직 제한적");
    if (!available.length) summaryParts.push("연결된 세부 지표가 아직 없음");
    const missing = metrics.filter((metric) => !metric.available).map((metric) => metric.label);
    const warnings = [];
    if (conflict) warnings.push(`신호 충돌: ${positiveMetrics.map((metric) => metric.label).join("·")} 우호 / ${negativeMetrics.map((metric) => metric.label).join("·")} 주의`);
    if (missing.length) warnings.push(`미확인 지표: ${missing.join("·")}`);
    if (metrics.find((metric) => metric.key === "market")?.relevance === "broad") warnings.push("시장 영향은 종목 직접 연결이 아닌 광역 시장 영향으로 반영");

    return {
      version: VERSION,
      code: compact(code || quant?.code || dashboard?.code || fallbackDetail?.code),
      name: compact(quant?.name || dashboard?.name || homeContext?.name || fallbackDetail?.name) || "관심종목",
      asOf: newestAsOf(
        quant?.as_of,
        dashboard?.as_of,
        homeContext?.as_of,
        marketImpact?.as_of,
        metrics.map((metric) => metric.asOf),
      ),
      stance,
      tone,
      action,
      score: round(weightedScore),
      scoreDisplay: signed(weightedScore),
      confidence,
      coverageCount: available.length,
      coverageWeight: effectiveWeight,
      coverageLabel: `${available.length}/6개 · 가중 ${effectiveWeight}%`,
      lead: `차트 ${WEIGHTS.chart} · 수급 ${WEIGHTS.flow} · 공시 ${WEIGHTS.disclosure} · 뉴스 ${WEIGHTS.news} · 리포트 ${WEIGHTS.research} · 시장 ${WEIGHTS.market} 가중 종합 · 현재 반영 ${effectiveWeight}%`,
      summary: `${summaryParts.join(" · ")}. ${quantLabel ? `현재 시그널은 ${quantLabel}입니다. ` : ""}${hardRisk ? "중대 공시는 종합점수보다 우선합니다." : "자료 부족과 신호 충돌은 신뢰도에 반영했습니다."}`,
      signalAction: quantAction || null,
      signalLabel: quantLabel || null,
      conflict,
      hardRisk,
      limited,
      entryAllowed: quant?.confirmation?.entry_allowed === true,
      decisionLevels: responseDecisionLevels(dashboard, quant),
      metrics,
      warnings,
      nextChecks: nextChecks(metrics, dashboard, quant, hardRisk),
    };
  };

  return Object.freeze({ VERSION, WEIGHTS, buildResponse, buildInvestorGuide });
}));
