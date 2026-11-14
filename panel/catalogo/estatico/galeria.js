// Filtro por categoría de la galería. Sin JS se ven todas las tarjetas (los botones están ocultos).
(function () {
  var barra = document.querySelector(".filtros");
  if (!barra) return;
  barra.hidden = false;
  barra.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("button[data-filtro]");
    if (!b) return;
    var cat = b.dataset.filtro;
    barra.querySelectorAll("button").forEach(function (x) {
      x.setAttribute("aria-pressed", x === b ? "true" : "false");
    });
    document.querySelectorAll(".tarjeta").forEach(function (t) {
      t.hidden = cat !== "" && t.dataset.categoria !== cat;
    });
  });
})();
