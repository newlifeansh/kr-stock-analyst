// Installed only in the canonical /us shell served through the domestic
// front door. Every same-origin data request must use the US service; an
// unavailable US service must never fall back to the domestic database.
(() => {
  const prefix = "/us-gateway";
  const nativeFetch = window.fetch.bind(window);
  window.__US_PUBLIC_GATEWAY__ = prefix;
  window.fetch = (input, init) => {
    const inputUrl = input instanceof Request ? input.url : input;
    let url;
    try {
      url = new URL(inputUrl, window.location.href);
    } catch {
      return nativeFetch(input, init);
    }
    if (url.origin !== window.location.origin || url.pathname.startsWith(`${prefix}/`)) {
      return nativeFetch(input, init);
    }
    url.pathname = `${prefix}${url.pathname}`;
    return nativeFetch(input instanceof Request ? new Request(url, input) : url.href, init);
  };
})();
