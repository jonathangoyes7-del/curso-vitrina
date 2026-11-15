// Botones de la página de pieza: «Compartir» y «Copiar código». Sin dependencias.
// Compartir: navigator.share → portapapeles ("Enlace copiado") → enlace seleccionado.
(function () {
  function aviso(id, texto) {
    var e = document.getElementById(id);
    if (e) e.textContent = texto;
  }

  async function copiar(texto) {
    if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("sin portapapeles");
    await navigator.clipboard.writeText(texto);
  }

  function mostrarEnlace(url) {
    var campo = document.getElementById("enlace-compartir");
    if (!campo) {
      campo = document.createElement("input");
      campo.id = "enlace-compartir";
      campo.type = "text";
      campo.readOnly = true;
      campo.setAttribute("aria-label", "Enlace de la pieza");
      document.getElementById("estado-compartir").after(campo);
    }
    campo.value = url;
    campo.focus();
    campo.select();
    aviso("estado-compartir", "Copia el enlace:");
  }

  async function compartir(boton) {
    var datos = { title: boton.dataset.titulo, url: boton.dataset.url };
    if (navigator.share) {
      try { await navigator.share(datos); return; }
      catch (e) { if (e && e.name === "AbortError") return; /* la persona cerró el menú */ }
    }
    try { await copiar(datos.url); aviso("estado-compartir", "Enlace copiado"); }
    catch (e) { mostrarEnlace(datos.url); }
  }

  async function copiarCodigo(boton) {
    var campo = document.getElementById(boton.dataset.copiar);
    try { await copiar(campo.value); aviso("estado-copiar", "Código copiado"); }
    catch (e) { campo.focus(); campo.select(); aviso("estado-copiar", "Selecciona y copia el código."); }
  }

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("button");
    if (!b) return;
    if (b.hasAttribute("data-compartir")) compartir(b);
    else if (b.hasAttribute("data-copiar")) copiarCodigo(b);
  });
})();
