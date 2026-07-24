const tabs = [...document.querySelectorAll("[data-concept]")];
const panels = [...document.querySelectorAll("[data-panel]")];

function showConcept(name) {
  tabs.forEach((tab) => {
    const active = tab.dataset.concept === name;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-pressed", String(active));
  });
  panels.forEach((panel) => {
    const active = panel.dataset.panel === name;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  });
  history.replaceState(null, "", `#${name}`);
}

tabs.forEach((tab) => tab.addEventListener("click", () => showConcept(tab.dataset.concept)));

document.querySelectorAll(".period-control button").forEach((button) => {
  button.addEventListener("click", () => {
    button.parentElement.querySelectorAll("button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
  });
});

document.querySelector("[data-watch]")?.addEventListener("click", (event) => {
  const button = event.currentTarget;
  const active = button.classList.toggle("is-added");
  button.innerHTML = active ? "<span>✓</span> 관심종목 추가됨" : "<span>＋</span> 관심종목";
});

document.querySelector("[data-add-signal]")?.addEventListener("click", (event) => {
  const button = event.currentTarget;
  button.textContent = "✓ 시그널 생성됨";
  button.classList.add("is-done");
  window.setTimeout(() => {
    button.textContent = "＋ 새 시그널";
    button.classList.remove("is-done");
  }, 1800);
});

const initial = location.hash.slice(1);
if (["pulse", "lens", "signals"].includes(initial)) showConcept(initial);
