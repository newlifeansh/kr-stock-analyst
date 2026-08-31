/* Adaptive appearance bootstrap. Runs in <head> before the theme CSS. */
(() => {
  "use strict";

  const root = document.documentElement;
  const darkMode = window.matchMedia("(prefers-color-scheme: dark)");
  const requestedTheme = new URLSearchParams(window.location.search)
    .get("theme")
    ?.trim()
    .toLowerCase();
  const fixedTheme = requestedTheme === "light" || requestedTheme === "dark"
    ? requestedTheme
    : "";

  const resolvedTheme = () => fixedTheme || (darkMode.matches ? "dark" : "light");

  const applyTheme = () => {
    const theme = resolvedTheme();
    const isDark = theme === "dark";
    root.dataset.stagingTheme = theme;
    root.style.colorScheme = theme;

    const themeColor = document.getElementById("staging-theme-color");
    if (themeColor instanceof HTMLMetaElement) {
      themeColor.content = isDark ? "#17161b" : "#ffffff";
    }

    const darkFallback = document.querySelector("[data-staging-dark-fallback]");
    if (darkFallback instanceof HTMLLinkElement) {
      darkFallback.media = fixedTheme
        ? (isDark ? "all" : "not all")
        : "(prefers-color-scheme: dark)";
    }

    if (document.body) {
      document.body.dataset.stagingTheme = theme;
    }
  };

  applyTheme();
  document.addEventListener("DOMContentLoaded", applyTheme, { once: true });

  const handleSystemThemeChange = () => {
    if (!fixedTheme) applyTheme();
  };
  if (typeof darkMode.addEventListener === "function") {
    darkMode.addEventListener("change", handleSystemThemeChange);
  } else if (typeof darkMode.addListener === "function") {
    darkMode.addListener(handleSystemThemeChange);
  }
})();
