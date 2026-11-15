// Búsqueda y filtro por categoría de la galería. Sin JS se ven todas las tarjetas (los controles están ocultos).
(function () {
  var barra = document.querySelector(".filtros");
  var buscador = document.querySelector(".buscador");
  var caja = document.getElementById("buscar");
  var aviso = document.querySelector(".sin-resultados");
  if (!barra) return;
  barra.hidden = false;
  if (buscador) buscador.hidden = false;

  var categoria = "";

  // Minúsculas y sin tildes: «CÁNTARO» y «cantaro» son lo mismo.
  function normalizar(texto) {
    return String(texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  function aplicar() {
    var consulta = caja ? normalizar(caja.value) : "";
    var visibles = 0;
    document.querySelectorAll(".tarjeta").forEach(function (t) {
      var cumpleCategoria = categoria === "" || t.dataset.categoria === categoria;
      var cumpleBusqueda = consulta === "" ||
        normalizar(t.dataset.nombre).indexOf(consulta) !== -1 ||
        normalizar(t.dataset.categoria).indexOf(consulta) !== -1;
      t.hidden = !(cumpleCategoria && cumpleBusqueda);
      if (!t.hidden) visibles++;
    });
    if (aviso) aviso.hidden = visibles !== 0;
  }

  barra.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("button[data-filtro]");
    if (!b) return;
    categoria = b.dataset.filtro;
    barra.querySelectorAll("button").forEach(function (x) {
      x.setAttribute("aria-pressed", x === b ? "true" : "false");
    });
    aplicar();
  });
  if (caja) caja.addEventListener("input", aplicar);
})();
