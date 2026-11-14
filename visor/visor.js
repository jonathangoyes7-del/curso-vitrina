// Visor 3D compartido (página de pieza, incrustación, panel y Reel).
// Lo importan las páginas con un mapa de importación que define `three`, `three/addons/` y `@sparkjsdev/spark`.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { SparkRenderer, SplatMesh } from "@sparkjsdev/spark";

const RADIO = 2.5;            // distancia de la cámara al objetivo (docs/pico-idol.md)
const ELEVACION = 0.1;        // rad, para ver un poco desde arriba
const DISTANCIA_MINIMA = 1.6; // la pieza cabe en una esfera de ~0,7 de radio (docs/pico-idol.md): así la cámara nunca la atraviesa
const DISTANCIA_MAXIMA = 4;
const VELOCIDAD_GIRO = 1;     // 1 = una vuelta por minuto
const MENSAJE_ERROR = "No se pudo cargar la pieza en 3D.";

function colorPapel(contenedor) {
  const v = getComputedStyle(contenedor).getPropertyValue("--papel").trim();
  return v || "#F5F1E8";
}

const dosCuadros = () => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)));

function botonVistaInicial(contenedor, api) {
  if (getComputedStyle(contenedor).position === "static") contenedor.style.position = "relative";
  const b = document.createElement("button");
  b.type = "button";
  b.className = "visor-vista-inicial";
  b.textContent = "Vista inicial";
  b.style.cssText = "position:absolute;right:12px;bottom:12px;min-height:44px;padding:0 14px;font:600 .9rem system-ui,sans-serif;"
    + "color:var(--cobalto,#2347A8);background:var(--papel,#F5F1E8);border:1px solid var(--cobalto,#2347A8);border-radius:6px;cursor:pointer";
  b.addEventListener("click", () => api.vistaInicial());
  return b;
}

export async function montarVisor(contenedor, { urlSplat, modo = "pagina" }) {
  document.body.dataset.visor = "cargando";
  const reel = modo === "reel";

  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: reel });
  renderer.setPixelRatio(reel ? 1 : Math.min(devicePixelRatio, 2));
  renderer.setClearColor(colorPapel(contenedor));
  const ancho = () => Math.max(contenedor.clientWidth, 1);
  const alto = () => Math.max(contenedor.clientHeight, 1);
  renderer.setSize(ancho(), alto());
  contenedor.appendChild(renderer.domElement);
  renderer.domElement.style.display = "block";

  const escena = new THREE.Scene();
  const camara = new THREE.PerspectiveCamera(50, ancho() / alto(), 0.01, 100);
  escena.add(new SparkRenderer({ renderer }));

  const objetivo = new THREE.Vector3(0, 0, 0);
  const colocar = (azimut) => {
    camara.position.set(
      objetivo.x + RADIO * Math.sin(azimut) * Math.cos(ELEVACION),
      objetivo.y + RADIO * Math.sin(ELEVACION),
      objetivo.z + RADIO * Math.cos(azimut) * Math.cos(ELEVACION),
    );
    camara.lookAt(objetivo);
  };
  colocar(0);

  let controles = null;
  // El amortiguado (damping) deja girando la cámara un rato más: se vacía para que pare en seco.
  const sinInercia = () => {
    controles.enableDamping = false;
    controles.update();
    controles.enableDamping = true;
  };
  if (!reel) {
    controles = new OrbitControls(camara, renderer.domElement);
    controles.target.copy(objetivo);
    controles.enableDamping = true;
    controles.enablePan = false;           // sin desplazamiento lateral
    controles.minDistance = DISTANCIA_MINIMA;
    controles.maxDistance = DISTANCIA_MAXIMA;
    controles.maxPolarAngle = Math.PI / 2;  // no se puede mirar desde debajo del horizonte
    controles.autoRotate = true;            // gira solo, despacio, hasta que alguien lo toque
    controles.autoRotateSpeed = VELOCIDAD_GIRO;
    controles.addEventListener("start", () => { controles.autoRotate = false; sinInercia(); });
    controles.update();
    controles.saveState();                  // vista del principio, para el botón
  }

  let ultimo = performance.now();
  const dibujar = () => {
    const ahora = performance.now();
    controles?.update((ahora - ultimo) / 1000);   // con el tiempo real, el giro no depende de los fps
    ultimo = ahora;
    renderer.render(escena, camara);
  };
  const observador = new ResizeObserver(() => {
    renderer.setSize(ancho(), alto());
    camara.aspect = ancho() / alto();
    camara.updateProjectionMatrix();
    if (reel) dibujar();
  });
  observador.observe(contenedor);

  let destruido = false;
  const api = {
    azimut: () => Math.atan2(camara.position.x - objetivo.x, camara.position.z - objetivo.z),
    altura: () => camara.position.y - objetivo.y,
    distancia: () => camara.position.distanceTo(objetivo),
    girando: () => !!controles?.autoRotate,
    vistaInicial() { if (!controles) return; sinInercia(); controles.reset(); },
    async irACuadro(i, total) {
      colocar((2 * Math.PI * i) / total);
      dibujar();
      await dosCuadros();
      dibujar();   // Spark ordena los gaussianos en cada render: se repite para que el cuadro salga completo
    },
    destruir() {
      destruido = true;
      observador.disconnect();
      renderer.setAnimationLoop(null);
      controles?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };

  try {
    const splat = new SplatMesh({ url: urlSplat });
    splat.quaternion.set(1, 0, 0, 0);   // el PLY de Idol sale boca abajo (docs/pico-idol.md)
    escena.add(splat);
    await splat.initialized;
  } catch (e) {
    console.error(e);
    api.destruir();
    const aviso = document.createElement("p");
    aviso.className = "visor-error";
    aviso.textContent = MENSAJE_ERROR;
    aviso.setAttribute("role", "alert");
    aviso.style.cssText = "margin:0;padding:2rem;text-align:center;color:#2E2D2B;font:1rem system-ui,sans-serif";
    contenedor.appendChild(aviso);
    document.body.dataset.visor = "error";
    return api;
  }

  if (destruido) return api;
  if (reel) dibujar();
  else {
    renderer.setAnimationLoop(dibujar);
    contenedor.appendChild(botonVistaInicial(contenedor, api));
  }
  document.body.dataset.visor = "listo";
  return api;
}
