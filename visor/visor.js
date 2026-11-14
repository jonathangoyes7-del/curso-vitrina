// Visor 3D compartido (página de pieza, incrustación, panel y Reel).
// Lo importan las páginas con un mapa de importación que define `three`, `three/addons/` y `@sparkjsdev/spark`.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { SparkRenderer, SplatMesh } from "@sparkjsdev/spark";

const RADIO = 2.5;            // distancia de la cámara al objetivo (docs/pico-idol.md)
const ELEVACION = 0.1;        // rad, para ver un poco desde arriba
const MENSAJE_ERROR = "No se pudo cargar la pieza en 3D.";

function colorPapel(contenedor) {
  const v = getComputedStyle(contenedor).getPropertyValue("--papel").trim();
  return v || "#F5F1E8";
}

const dosCuadros = () => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)));

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
  if (!reel) {
    controles = new OrbitControls(camara, renderer.domElement);
    controles.target.copy(objetivo);
    controles.enableDamping = true;
    controles.enablePan = false;           // sin desplazamiento lateral
    controles.minDistance = 1.2;
    controles.maxDistance = 4;
    controles.update();
  }

  const dibujar = () => { controles?.update(); renderer.render(escena, camara); };
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
  else renderer.setAnimationLoop(dibujar);
  document.body.dataset.visor = "listo";
  return api;
}
