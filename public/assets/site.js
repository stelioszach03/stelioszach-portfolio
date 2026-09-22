const menu = document.querySelector(".menu-toggle");
const navigation = document.getElementById("primary-navigation");
if (menu && navigation) {
  const setMenu = (open) => {
    menu.setAttribute("aria-expanded", String(open));
    navigation.toggleAttribute("data-open", open);
  };
  menu.hidden = false;
  document.documentElement.classList.add("enhanced");
  menu.addEventListener("click", () =>
    setMenu(menu.getAttribute("aria-expanded") !== "true"),
  );
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMenu(false);
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      menu.getAttribute("aria-expanded") === "true"
    ) {
      setMenu(false);
      menu.focus();
    }
  });
  matchMedia("(min-width: 901px)").addEventListener("change", () =>
    setMenu(false),
  );
}
