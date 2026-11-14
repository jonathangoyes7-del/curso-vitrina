const H = { "X-Vitrina": "panel" };
const lista = document.getElementById("lista");
const aviso = document.getElementById("aviso");
const conexion = document.getElementById("conexion");
const clase = (estado) => estado.replace(/\s+/g, "-");

function tarjeta(p) {
  const d = document.createElement("article");
  d.className = "pieza " + clase(p.estado);
  // La portada solo existe cuando ya se procesó la foto; si no carga, queda el hueco gris.
  const foto = document.createElement("img");
  foto.src = `/api/piezas/${p.id}/archivos/portada.jpg`;
  foto.alt = p.nombre ? "Foto de " + p.nombre : "Foto de la pieza " + p.id;
  foto.loading = "lazy";
  foto.onerror = () => { const h = document.createElement("div"); h.className = "sin-foto"; h.textContent = "Sin foto"; foto.replaceWith(h); };
  const cuerpo = document.createElement("div");
  cuerpo.className = "cuerpo";
  const nombre = document.createElement("strong");
  nombre.textContent = p.nombre || `Pieza ${p.id}`;
  const estado = document.createElement("span");
  estado.className = "estado";
  estado.textContent = p.estado;
  cuerpo.append(nombre, estado);
  d.append(foto, cuerpo);
  if (p.estado === "pendiente" || p.estado === "procesando") {
    const barra = document.createElement("progress");
    barra.max = 100; barra.value = p.porcentaje;
    barra.setAttribute("aria-label", "Progreso de la pieza " + p.id);
    cuerpo.append(barra);
  }
  if (p.error_legible) {
    const e = document.createElement("p");
    e.className = "error";
    e.textContent = p.error_legible.titulo + ". " + p.error_legible.sugerencia;
    const t = document.createElement("small");
    t.textContent = "Detalle técnico: " + p.error_legible.tecnico;
    e.append(t);
    cuerpo.append(e);
  }
  if (p.puede_reintentar) {
    const b = document.createElement("button");
    b.textContent = "Reintentar";
    b.onclick = async () => {
      b.disabled = true;
      const r = await fetch(`/api/piezas/${p.id}/reintentar`, { method: "POST", headers: H });
      if (!r.ok) { aviso.textContent = "No se pudo reintentar."; b.disabled = false; }
    };
    cuerpo.append(b);
  }
  return d;
}

function pintar(piezas) {
  lista.replaceChildren(...piezas.map(tarjeta));
}

// El servidor avisa cuando algo cambia: la página no pregunta cada pocos segundos.
const origen = new EventSource("/api/eventos");
origen.addEventListener("piezas", (e) => { conexion.textContent = "En vivo"; pintar(JSON.parse(e.data)); });
origen.onerror = () => { conexion.textContent = "Reconectando…"; };

document.getElementById("subida").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  aviso.textContent = "";
  const r = await fetch("/api/piezas", { method: "POST", headers: H, body: new FormData(ev.target) });
  if (r.status === 422) {
    const j = await r.json();
    aviso.textContent = "Foto rechazada: " + (j.problemas || []).join(" ");
  } else if (!r.ok) {
    aviso.textContent = "No se pudo subir la foto.";
  } else {
    ev.target.reset();
  }
});
