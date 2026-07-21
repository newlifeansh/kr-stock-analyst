const menuButton = document.querySelector("#menu-button");
const portfolioNav = document.querySelector("#portfolio-nav");
const imageDialog = document.querySelector("#image-dialog");
const dialogImage = document.querySelector("#dialog-image");
const dialogClose = document.querySelector("#dialog-close");

menuButton?.addEventListener("click", () => {
  const isOpen = portfolioNav.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(isOpen));
});

portfolioNav?.addEventListener("click", (event) => {
  if (!event.target.closest("a")) return;
  portfolioNav.classList.remove("open");
  menuButton?.setAttribute("aria-expanded", "false");
});

document.querySelectorAll("[data-lightbox-src]").forEach((button) => {
  button.addEventListener("click", () => {
    dialogImage.src = button.dataset.lightboxSrc || "";
    dialogImage.alt = button.dataset.lightboxAlt || "비밀노트 모바일 화면";
    imageDialog.showModal();
  });
});

dialogClose?.addEventListener("click", () => imageDialog.close());

imageDialog?.addEventListener("click", (event) => {
  if (event.target === imageDialog) imageDialog.close();
});
