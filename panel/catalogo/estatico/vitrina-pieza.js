// <vitrina-pieza pieza="slug"> — muestra una pieza de Vitrina en 3D en cualquier web.
// Uso (una línea): <script type="module" src=".../componente/vitrina-pieza.js"></script><vitrina-pieza pieza="slug"></vitrina-pieza>
// Atributos: pieza (obligatorio), alto (px, por defecto 480).
// El sitio se deduce de dónde se cargó este archivo (…/componente/vitrina-pieza.js → …/).
const BASE = new URL("../", import.meta.url).href;
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

class VitrinaPieza extends HTMLElement {
  static observedAttributes = ["pieza", "alto"];

  connectedCallback() {
    if (!this.shadowRoot) {
      const raiz = this.attachShadow({ mode: "open" });
      raiz.innerHTML = '<style>:host{display:block}iframe{display:block;width:100%;border:0}</style>';
    }
    this.#pintar();
  }

  attributeChangedCallback() { if (this.isConnected) this.#pintar(); }

  #pintar() {
    const raiz = this.shadowRoot;
    raiz.querySelector("iframe")?.remove();
    const slug = this.getAttribute("pieza") || "";
    if (!SLUG.test(slug)) return;   // sin pieza válida no se pinta nada; la web anfitriona no se rompe
    const alto = parseInt(this.getAttribute("alto"), 10);
    const marco = document.createElement("iframe");
    marco.src = `${BASE}embed/${slug}/`;
    marco.title = "Pieza en 3D";
    marco.loading = "lazy";
    marco.allowFullscreen = true;
    marco.setAttribute("allow", "fullscreen");
    marco.style.height = `${alto > 0 ? alto : 480}px`;
    raiz.append(marco);
  }
}

if (!customElements.get("vitrina-pieza")) customElements.define("vitrina-pieza", VitrinaPieza);
