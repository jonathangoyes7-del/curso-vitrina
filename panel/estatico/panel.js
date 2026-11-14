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
    const etapa = document.createElement("p");
    etapa.className = "etapa";
    const donde = p.estado === "pendiente" ? "En espera" : (p.etapa_texto || "Empezando");
    etapa.textContent = `${donde} · ${p.porcentaje} %`;
    cuerpo.append(etapa, barra);
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

const resultados = document.getElementById("resultados");
const zona = document.getElementById("zona");

function anotar(nombre, clase, texto) {
  const li = document.createElement("li");
  li.className = clase;
  li.textContent = `${nombre}: ${texto}`;
  resultados.append(li);
}

// Una foto cada vez: el servidor las procesa de una en una de todos modos.
async function subirUna(archivo) {
  const datos = new FormData();
  datos.append("foto", archivo);
  try {
    const r = await fetch("/api/piezas", { method: "POST", headers: H, body: datos });
    if (r.ok) return anotar(archivo.name, "subida", "subida, entra en la cola.");
    if (r.status === 422) {
      const j = await r.json();
      return anotar(archivo.name, "rechazada", "rechazada. " + (j.problemas || []).join(" "));
    }
    anotar(archivo.name, "rechazada", "no se pudo subir.");
  } catch {
    anotar(archivo.name, "rechazada", "no se pudo subir (sin conexión con el panel).");
  }
}

let turno = Promise.resolve();
function subir(archivos) {
  const fotos = [...archivos];
  if (!fotos.length) return;
  // Cada tanda espera a la anterior y reemplaza los resultados de la tanda previa.
  turno = turno.then(async () => {
    resultados.replaceChildren();
    for (const f of fotos) await subirUna(f);
  });
}

document.getElementById("subida").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const entrada = ev.target.elements.foto;
  subir(entrada.files);
  ev.target.reset();
});

for (const tipo of ["dragenter", "dragover"]) {
  zona.addEventListener(tipo, (ev) => { ev.preventDefault(); zona.classList.add("arrastrando"); });
}
zona.addEventListener("dragleave", (ev) => { if (!zona.contains(ev.relatedTarget)) zona.classList.remove("arrastrando"); });
zona.addEventListener("drop", (ev) => {
  ev.preventDefault();
  zona.classList.remove("arrastrando");
  subir(ev.dataTransfer.files);
});
// Soltar una foto fuera de la zona no debe abrirla en el navegador.
for (const tipo of ["dragover", "drop"]) window.addEventListener(tipo, (ev) => ev.preventDefault());
