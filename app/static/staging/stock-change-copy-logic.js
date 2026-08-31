/*
 * Secret Note — friendly stock-change context copy
 *
 * Resolve the label from real quote/session dates instead of calendar-day
 * guesses so weekends and exchange holidays stay accurate.
 */
(function attachStockChangeCopyLogic(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SecretNoteStockChangeCopy = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function createStockChangeCopyLogic() {
  "use strict";

  const VERSION = "20260830-friendly-stock-change-v1";
  const KOREAN_WEEKDAYS = Object.freeze([
    "일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일",
  ]);

  const normalizeDate = (value) => {
    const candidate = String(value || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(candidate)) return "";
    const parsed = new Date(`${candidate}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== candidate) return "";
    return candidate;
  };

  const previousCalendarDate = (value) => {
    const normalized = normalizeDate(value);
    if (!normalized) return "";
    const parsed = new Date(`${normalized}T00:00:00Z`);
    parsed.setUTCDate(parsed.getUTCDate() - 1);
    return parsed.toISOString().slice(0, 10);
  };

  const weekdayLabel = (value) => {
    const normalized = normalizeDate(value);
    if (!normalized) return "";
    return KOREAN_WEEKDAYS[new Date(`${normalized}T00:00:00Z`).getUTCDay()] || "";
  };

  const normalizedTradeDates = (values) => Array.from(new Set(
    (Array.isArray(values) ? values : []).map(normalizeDate).filter(Boolean),
  )).sort();

  const resolveChangeContext = ({
    currentDate,
    quoteTradeDate,
    tradeDates = [],
    sessionStarted,
  } = {}) => {
    const today = normalizeDate(currentDate);
    const dates = normalizedTradeDates(tradeDates);
    let quoteDate = normalizeDate(quoteTradeDate);
    if (!quoteDate && today) {
      quoteDate = dates.filter((value) => value <= today).at(-1) || "";
    }

    const started = typeof sessionStarted === "boolean"
      ? sessionStarted
      : Boolean(today && quoteDate === today);
    if (today && quoteDate === today && started) {
      const referenceDate = dates.filter((value) => value < quoteDate).at(-1) || "";
      const yesterday = previousCalendarDate(today);
      const referenceWeekday = weekdayLabel(referenceDate);
      return Object.freeze({
        label: referenceDate === yesterday
          ? "어제보다"
          : referenceWeekday ? `${referenceWeekday}보다` : "지난 장보다",
        mode: "current-session",
        quoteDate,
        referenceDate,
      });
    }

    let completedDate = quoteDate;
    if (today && (!started || quoteDate !== today) && quoteDate === today) {
      completedDate = dates.filter((value) => value < today).at(-1) || "";
    }
    if (!completedDate && today) {
      completedDate = dates.filter((value) => value < today).at(-1) || "";
    }
    const yesterday = previousCalendarDate(today);
    const completedWeekday = weekdayLabel(completedDate);
    return Object.freeze({
      label: completedDate && completedDate === yesterday
        ? "어제 장에서"
        : completedWeekday ? `${completedWeekday} 장에서` : "최근 장에서",
      mode: "completed-session",
      quoteDate: completedDate,
      referenceDate: "",
    });
  };

  return Object.freeze({
    VERSION,
    normalizeDate,
    previousCalendarDate,
    weekdayLabel,
    resolveChangeContext,
  });
}));
