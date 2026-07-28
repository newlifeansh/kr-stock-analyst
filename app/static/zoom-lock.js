(function lockViewportZoom() {
  const preventGesture = (event) => event.preventDefault();
  const preventPinch = (event) => {
    if (event.touches && event.touches.length > 1) {
      event.preventDefault();
    }
  };

  document.documentElement.style.touchAction = "pan-x pan-y";
  document.addEventListener("touchmove", preventPinch, { passive: false });
  ["gesturestart", "gesturechange", "gestureend"].forEach((eventName) => {
    document.addEventListener(eventName, preventGesture, { passive: false });
  });
})();
