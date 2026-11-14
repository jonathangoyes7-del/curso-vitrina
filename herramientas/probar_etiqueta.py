"""Abre la web de prueba de la etiqueta <vitrina-pieza>, sin el panel.

Levanta dos servidores locales en puertos distintos (por tanto, orígenes distintos, como en la vida real):
  - el «sitio de Vitrina» (http://127.0.0.1:8771/): componente, página embed, splat, visor y librerías;
  - la «otra web» (http://127.0.0.1:8772/): `herramientas/web_ajena/index.html`, con la etiqueta pegada.

Uso:  uv run python herramientas/probar_etiqueta.py        (Ctrl+C para parar)
"""
from __future__ import annotations

import shutil
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from panel.catalogo.prueba import preparar_sitio  # noqa: E402

PUERTO_SITIO, PUERTO_WEB = 8771, 8772
SLUG = "pieza-de-prueba"
SITIO = RAIZ / "datos" / "prueba-etiqueta" / "sitio"
WEB = RAIZ / "herramientas" / "web_ajena"


class Manejador(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")   # como GitHub Pages
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def servir(carpeta: Path, puerto: int) -> ThreadingHTTPServer:
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), partial(Manejador, directory=str(carpeta)))
    Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


def main() -> None:
    if SITIO.exists():
        shutil.rmtree(SITIO)   # solo esta carpeta de pruebas, dentro de datos/
    preparar_sitio(SITIO, RAIZ, SLUG, RAIZ / "tests" / "fixtures" / "mini.spz")
    servidores = [servir(SITIO, PUERTO_SITIO), servir(WEB, PUERTO_WEB)]
    url = f"http://127.0.0.1:{PUERTO_WEB}/"
    print(f"Sitio de Vitrina: http://127.0.0.1:{PUERTO_SITIO}/\nOtra web (ábrela): {url}\nCtrl+C para parar.")
    webbrowser.open(url)
    try:
        Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for s in servidores:
            s.shutdown()


if __name__ == "__main__":
    main()
