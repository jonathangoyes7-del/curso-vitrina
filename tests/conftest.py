import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from panel.config import Config


@pytest.fixture
def config_tmp(tmp_path):
    """Config con `datos` y `sitio` dentro de tmp_path."""
    return Config(
        datos=tmp_path / "datos",
        sitio=tmp_path / "sitio",
        raiz=tmp_path,
    )


@pytest.fixture(scope="session")
def navegador():
    """Chromium de Playwright con aceleración por GPU (ANGLE/D3D11), compartido por los tests `navegador`."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
        yield nav
        nav.close()


def servir_carpetas(rutas: dict):
    """Servidor estático en un puerto libre: `rutas` mapea prefijos URL (`/visor`) a carpetas.

    Devuelve (servidor, URL base).
    """
    import functools
    import socket
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class Manejador(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            ruta = path.split("?", 1)[0].split("#", 1)[0]
            for prefijo, carpeta in rutas.items():
                if ruta == prefijo or ruta.startswith(prefijo + "/"):
                    return str(Path(carpeta) / ruta[len(prefijo):].lstrip("/"))
            return str(Path(__file__).parent / "_no_existe")

        def log_message(self, *args):
            pass

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{puerto}"


@pytest.fixture(scope="session")
def servidor_estatico():
    """Sirve /visor, /vendor/three, /vendor/spark y /fixtures. Devuelve la URL base."""
    raiz = Path(__file__).resolve().parent.parent
    servidor, url = servir_carpetas({
        "/visor": raiz / "visor",
        "/vendor/three": raiz / "node_modules" / "three",
        "/vendor/spark": raiz / "node_modules" / "@sparkjsdev" / "spark" / "dist",
        "/fixtures": raiz / "tests" / "fixtures",
    })
    yield url
    servidor.shutdown()


def _servir(app):
    import socket
    import threading
    import time

    import uvicorn

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning",
                                                timeout_graceful_shutdown=2))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.02)
    return servidor, hilo, f"http://127.0.0.1:{puerto}"


@pytest.fixture
def panel_vivo(config_tmp):
    """Panel en un puerto libre de 127.0.0.1, con dos piezas: una aprobada y una en borrador.

    Devuelve la URL. Sin trabajador: solo se prueba lo que la lista muestra.
    """
    from pathlib import Path

    from PIL import Image

    from panel.api import crear_app
    from panel.cola import Cola
    from panel.ficha import Ficha

    config_tmp = replace(config_tmp, raiz=Path(__file__).resolve().parent.parent)  # para servir /visor y /vendor
    cola = Cola(config_tmp)
    for nombre, aprobar in (("Cuenco de gres", True), ("Jarra de barro", False)):
        id_ = cola.crear_pieza()
        borrador = cola.carpeta_borrador(id_)
        borrador.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (200, 120, 60)).save(borrador / "portada.jpg")
        shutil.copy(Path(__file__).parent / "fixtures" / "mini.spz", borrador / "pieza.spz")
        cola.guardar_ficha_borrador(id_, Ficha(nombre, "Gres", "Cerámica", "Lavar a mano."))
        cola.aplicar(id_, "empezar")
        cola.aplicar(id_, "terminar")
        if aprobar:
            cola.aprobar(id_)
    cola.cerrar()
    servidor, hilo, url = _servir(crear_app(config_tmp, etapas=[], iniciar_trabajador=False))
    yield url
    servidor.should_exit = True
    hilo.join(timeout=5)


class ControlEtapas:
    """Deja que un test decida cuándo avanza cada trabajo del panel (etapas falsas)."""

    def __init__(self):
        import threading
        self.en_curso = threading.Event()   # la etapa 3D ya empezó y informó 50 %
        self.seguir = threading.Event()     # el test la deja terminar


@pytest.fixture
def panel_con_cola(config_tmp):
    """Panel sin piezas y con trabajador real y dos etapas falsas ('3d' retenida y 'ficha').

    Devuelve (url, control). Un trabajo a la vez, como en producción: la etapa 3D espera a
    `control.seguir`, así el test puede mirar la barra con el trabajo a medias.
    """
    from panel.api import crear_app
    from panel.ficha import Ficha

    control = ControlEtapas()

    class Etapa3DRetenida:
        nombre = "3d"

        def __call__(self, ctx):
            ctx.informar(0.5)
            control.en_curso.set()
            control.seguir.wait(timeout=20)
            (ctx.borrador / "pieza.spz").write_bytes(b"spz")

    class EtapaFichaFalsa:
        nombre = "ficha"

        def __call__(self, ctx):
            ctx.cola.guardar_ficha_borrador(ctx.pieza.id, Ficha("Pieza de prueba", "Gres", "Cerámica", "Lavar a mano."))

    servidor, hilo, url = _servir(crear_app(config_tmp, etapas=[Etapa3DRetenida(), EtapaFichaFalsa()]))
    yield url, control
    control.seguir.set()
    servidor.should_exit = True
    hilo.join(timeout=10)
