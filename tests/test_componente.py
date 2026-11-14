"""Componente para incrustar (Tarea 12): <iframe>, página embed y etiqueta <vitrina-pieza>."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from panel.api import crear_app
from panel.catalogo.componente import (codigo_etiqueta, codigo_iframe, entorno_plantillas,
                                       renderizar_embed)
from panel.catalogo.modelos import PiezaPublica
from panel.catalogo.rutas import rutas_absolutas_locales
from panel.ficha import Ficha

URL = "https://jonathangoyes7-del.github.io/curso-vitrina/"
H = {"X-Vitrina": "panel"}
RAIZ = Path(__file__).resolve().parent.parent


def pieza(slug="cuenco", nombre="Cuenco", **extra):
    return PiezaPublica(slug=slug, ficha=Ficha(nombre, "Gres", "Cerámica", "Lavar a mano."),
                        es_ejemplo=False, credito_autor=None, credito_url=None,
                        carpeta=Path("vigente"), **extra)


def test_codigo_iframe():
    assert codigo_iframe(pieza(slug="cuenco-de-gres", nombre='Cuenco "azul"'), URL) == (
        '<iframe src="https://jonathangoyes7-del.github.io/curso-vitrina/embed/cuenco-de-gres/" '
        'title="Cuenco &#34;azul&#34; en 3D" width="100%" height="480" style="border:0" '
        'loading="lazy" allow="fullscreen"></iframe>')


def test_embed_rutas_relativas():
    html = renderizar_embed(pieza(slug="cuenco"))
    assert "../../piezas/cuenco/pieza.spz" in html and "Built with DINOv3" in html
    assert 'lang="es"' in html
    assert "../../vendor/three/three.module.js" in html
    assert not rutas_absolutas_locales(html)


def test_rutas_absolutas_locales():
    html = '<a href="/x">1</a><img src="//cdn/x.png"><a href="https://a/b"><script src="y.js">'
    assert rutas_absolutas_locales(html) == ["/x"]


def test_entorno_exige_variables():
    import jinja2
    with pytest.raises(jinja2.UndefinedError):
        entorno_plantillas().from_string("{{ falta }}").render()
    assert entorno_plantillas().from_string("{{ x }}").render(x="<b>") == "&lt;b&gt;"


def test_etiqueta_en_una_sola_linea():
    codigo = codigo_etiqueta("cuenco-de-gres", URL)
    assert codigo == (
        '<script type="module" src="https://jonathangoyes7-del.github.io/curso-vitrina/componente/'
        'vitrina-pieza.js"></script><vitrina-pieza pieza="cuenco-de-gres"></vitrina-pieza>')
    assert "\n" not in codigo


def test_etiqueta_rechaza_slug_raro():
    with pytest.raises(ValueError):
        codigo_etiqueta('x"><script>', URL)


# --- API del panel: el código se pide aunque la pieza no esté publicada -----------------------

@pytest.fixture
def cliente(config_tmp):
    app = crear_app(config_tmp, etapas=[], iniciar_trabajador=False)
    return TestClient(app, base_url="http://127.0.0.1"), app.state.cola


def test_api_etiqueta_de_pieza_sin_publicar(cliente):
    c, cola = cliente
    i = cola.crear_pieza()
    cola.guardar_ficha_borrador(i, Ficha("Jarra", "Barro", "Cerámica", "Lavar a mano."))
    cola.aplicar(i, "empezar"); cola.aplicar(i, "terminar")   # «para revisar», no publicada
    cola.fijar_slug(i, "jarra")
    r = c.get(f"/api/piezas/{i}/etiqueta")
    assert r.status_code == 200
    d = r.json()
    assert d["codigo"] == codigo_etiqueta("jarra", "https://jonathangoyes7-del.github.io/curso-vitrina/")
    assert d["publicada"] is False


def test_api_etiqueta_sin_slug_explica_por_que(cliente):
    c, cola = cliente
    i = cola.crear_pieza()
    r = c.get(f"/api/piezas/{i}/etiqueta")
    assert r.status_code == 409 and "dirección" in r.json()["detail"]


def test_api_etiqueta_pieza_inexistente(cliente):
    assert cliente[0].get("/api/piezas/999/etiqueta").status_code == 404


# --- Navegador: la etiqueta pegada en «otra web» muestra la pieza girando ---------------------

def _sitio_de_prueba(destino: Path, slug: str):
    from panel.catalogo.prueba import preparar_sitio
    preparar_sitio(destino, RAIZ, slug, RAIZ / "tests" / "fixtures" / "mini.spz")


@pytest.mark.navegador
def test_etiqueta_en_otra_web(navegador, tmp_path):
    from tests.conftest import servir_carpetas
    from tests.utilidades import varianza_de_pixeles
    sitio = tmp_path / "sitio"
    _sitio_de_prueba(sitio, "cuenco")
    srv_sitio, url_sitio = servir_carpetas({"": sitio})
    otra = tmp_path / "otra"
    otra.mkdir()
    # «Otra web»: otro puerto, es decir, otro origen, con la etiqueta pegada tal cual.
    (otra / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><h1>Mi tienda</h1>{codigo_etiqueta("cuenco", url_sitio + "/")}',
        encoding="utf-8")
    srv_otra, url_otra = servir_carpetas({"": otra})
    try:
        p = navegador.new_page(viewport={"width": 900, "height": 700})
        p.goto(url_otra + "/index.html")
        p.wait_for_selector("vitrina-pieza")
        marco = p.frame_locator("vitrina-pieza iframe")
        marco.locator("canvas").wait_for(timeout=30_000)
        frame = next(f for f in p.frames if "/embed/cuenco/" in f.url)
        frame.wait_for_function("document.body.dataset.visor === 'listo'", timeout=30_000)
        a1 = frame.evaluate("window.visor.azimut()")
        p.wait_for_timeout(1500)
        a2 = frame.evaluate("window.visor.azimut()")
        assert abs(a2 - a1) > 0.005, "la pieza no gira sola"
        assert varianza_de_pixeles(marco.locator("canvas").screenshot()) > 10
        assert p.locator("vitrina-pieza").evaluate("e => e.getBoundingClientRect().height") >= 400
    finally:
        srv_sitio.shutdown(); srv_otra.shutdown()


@pytest.mark.navegador
def test_etiqueta_sin_slug_valido_no_rompe_la_web(navegador, tmp_path):
    from tests.conftest import servir_carpetas
    sitio = tmp_path / "sitio"
    _sitio_de_prueba(sitio, "cuenco")
    srv, url = servir_carpetas({"": sitio})
    try:
        p = navegador.new_page()
        p.set_content(f'<script type="module" src="{url}/componente/vitrina-pieza.js"></script>'
                      '<vitrina-pieza pieza="../malo"></vitrina-pieza><p id="resto">sigue</p>')
        p.wait_for_timeout(500)
        assert p.locator("#resto").inner_text() == "sigue"
        assert p.locator("vitrina-pieza").evaluate("e => e.shadowRoot.querySelector('iframe')") is None
    finally:
        srv.shutdown()


@pytest.mark.navegador
def test_boton_copiar_etiqueta_en_pieza_sin_publicar(panel_vivo, navegador):
    ctx = navegador.new_context(permissions=["clipboard-read", "clipboard-write"])
    p = ctx.new_page()
    p.goto(panel_vivo)
    p.locator(".pieza", has_text="Jarra de barro").click()   # «para revisar»: no está publicada
    boton = p.get_by_role("button", name="Copiar código de la etiqueta")
    boton.click()
    p.get_by_text("Código copiado.").wait_for()
    assert p.evaluate("navigator.clipboard.readText()") == codigo_etiqueta(
        "jarra-de-barro", "https://jonathangoyes7-del.github.io/curso-vitrina/")
    assert "cuando la pieza esté publicada" in p.locator("#revision .mensaje").first.inner_text()


def test_web_ajena_lleva_la_etiqueta_actual():
    """La página de prueba tiene pegada exactamente la etiqueta que genera el código."""
    html = (RAIZ / "herramientas" / "web_ajena" / "index.html").read_text(encoding="utf-8")
    assert codigo_etiqueta("pieza-de-prueba", "http://127.0.0.1:8771/") in html
