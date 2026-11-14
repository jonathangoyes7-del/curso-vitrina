"""Página de pieza (Tarea 17): ficha, visor, QR, compartir y código para incrustar."""
from pathlib import Path

import pytest

from panel.catalogo.componente import codigo_iframe
from panel.catalogo.modelos import PiezaPublica
from panel.catalogo.pagina import renderizar_pieza
from panel.catalogo.rutas import rutas_absolutas_locales
from panel.ficha import Ficha

URL = "https://jonathangoyes7-del.github.io/curso-vitrina/"
RAIZ = Path(__file__).resolve().parent.parent


def pieza(slug="cuenco", nombre="Cuenco", **extra):
    datos = dict(es_ejemplo=False, credito_autor=None, credito_url=None)
    datos.update(extra)
    return PiezaPublica(slug=slug, ficha=Ficha(nombre, "Gres y esmalte", "Cerámica", "Lavar a mano."),
                        carpeta=Path("vigente"), **datos)


def test_og_absoluto_y_rutas_relativas():
    html = renderizar_pieza(pieza(slug="cuenco"), URL)
    assert f'content="{URL}piezas/cuenco/portada.jpg"' in html
    assert not rutas_absolutas_locales(html) and "Built with DINOv3" in html


def test_cabecera_social():
    html = renderizar_pieza(pieza(slug="cuenco", nombre="Cuenco azul"), URL)
    assert "<title>Cuenco azul · Vitrina</title>" in html
    assert '<meta name="description" content="Gres y esmalte">' in html
    assert '<meta property="og:type" content="website">' in html
    assert '<meta property="og:title" content="Cuenco azul">' in html
    assert '<meta property="og:description" content="Gres y esmalte">' in html
    assert f'<meta property="og:url" content="{URL}piezas/cuenco/">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert 'lang="es"' in html


def test_rutas_del_sitio_con_raiz_dos_niveles():
    html = renderizar_pieza(pieza(slug="cuenco"), URL)
    assert "../../vendor/three/three.module.js" in html
    assert "../../visor/visor.js" in html and "pieza.spz" in html and 'modo: "pagina"' in html
    assert '<script type="module">' in html
    assert 'src="qr.svg"' in html and 'alt="Código QR de Cuenco"' in html
    assert 'href="../../"' in html and "← Volver al catálogo" in html


def test_ficha_en_dl():
    html = renderizar_pieza(pieza(), URL)
    for etiqueta in ("Nombre", "Materiales", "Categoría", "Cuidados"):
        assert f"<dt>{etiqueta}</dt>" in html
    assert "<dd>Gres y esmalte</dd>" in html and "<dd>Lavar a mano.</dd>" in html


def test_codigo_para_incrustar_en_textarea():
    p = pieza(slug="cuenco", nombre='Cuenco "azul"')
    html = renderizar_pieza(p, URL)
    assert "<textarea" in html and "readonly" in html
    from markupsafe import escape
    assert str(escape(codigo_iframe(p, URL))) in html
    assert "Copiar código" in html and "Compartir" in html


def test_nombre_se_escapa():
    html = renderizar_pieza(pieza(nombre='<script>alert(1)</script>'), URL)
    assert "<script>alert(1)" not in html


def test_ejemplo_y_credito():
    html = renderizar_pieza(pieza(es_ejemplo=True, credito_autor="Ana Pérez", credito_url="https://unsplash.com/@ana"), URL)
    assert ">Ejemplo<" in html and 'href="https://unsplash.com/@ana"' in html and "Ana Pérez" in html
    assert "en Unsplash" in html


def test_sin_ejemplo_no_hay_etiqueta():
    html = renderizar_pieza(pieza(), URL)
    assert ">Ejemplo<" not in html and "Unsplash" not in html


def _escribir_pagina(destino: Path, p: PiezaPublica) -> Path:
    """Página + compartir.js + estilos en una carpeta con la misma disposición relativa que el sitio."""
    import shutil
    carpeta = destino / "piezas" / p.slug
    carpeta.mkdir(parents=True)
    (carpeta / "index.html").write_text(renderizar_pieza(p, URL), encoding="utf-8")
    est = RAIZ / "panel" / "catalogo" / "estatico"
    shutil.copy(est / "compartir.js", destino / "compartir.js")
    shutil.copy(est / "estilos.css", destino / "estilos.css")
    return carpeta / "index.html"


def _pagina_sin_visor(p, ruta):
    """El visor no interesa aquí: se bloquean los módulos para probar solo los botones."""
    p.route("**/visor/visor.js", lambda r: r.fulfill(body="", content_type="text/javascript"))
    p.goto(ruta.as_uri())


@pytest.mark.navegador
def test_compartir_sin_web_share_copia(navegador, tmp_path):
    ctx = navegador.new_context(permissions=["clipboard-read", "clipboard-write"])
    ctx.add_init_script("delete navigator.share")
    p = ctx.new_page()
    _pagina_sin_visor(p, _escribir_pagina(tmp_path, pieza()))
    p.get_by_role("button", name="Compartir").click()
    p.get_by_text("Enlace copiado").wait_for()
    assert p.evaluate("navigator.clipboard.readText()") == f"{URL}piezas/cuenco/"
    ctx.close()


@pytest.mark.navegador
def test_compartir_usa_web_share_si_existe(navegador, tmp_path):
    ctx = navegador.new_context()
    ctx.add_init_script("window.__compartido = null; navigator.share = async d => { window.__compartido = d; }")
    p = ctx.new_page()
    _pagina_sin_visor(p, _escribir_pagina(tmp_path, pieza(nombre="Cuenco azul")))
    p.get_by_role("button", name="Compartir").click()
    p.wait_for_function("window.__compartido !== null")
    assert p.evaluate("window.__compartido") == {"title": "Cuenco azul", "url": f"{URL}piezas/cuenco/"}
    ctx.close()


@pytest.mark.navegador
def test_compartir_sin_nada_muestra_el_enlace(navegador, tmp_path):
    ctx = navegador.new_context()   # sin permiso de portapapeles
    ctx.add_init_script("delete navigator.share; Object.defineProperty(navigator, 'clipboard', {value: undefined})")
    p = ctx.new_page()
    _pagina_sin_visor(p, _escribir_pagina(tmp_path, pieza()))
    p.get_by_role("button", name="Compartir").click()
    campo = p.locator("#enlace-compartir")
    campo.wait_for()
    assert campo.input_value() == f"{URL}piezas/cuenco/"
    assert p.evaluate("document.activeElement.id") == "enlace-compartir"
    ctx.close()


@pytest.mark.navegador
def test_copiar_codigo(navegador, tmp_path):
    ctx = navegador.new_context(permissions=["clipboard-read", "clipboard-write"])
    p = ctx.new_page()
    _pagina_sin_visor(p, _escribir_pagina(tmp_path, pieza()))
    p.get_by_role("button", name="Copiar código").click()
    p.get_by_text("Código copiado").wait_for()
    assert p.evaluate("navigator.clipboard.readText()") == codigo_iframe(pieza(), URL)
    ctx.close()


@pytest.mark.navegador
def test_pagina_con_visor_real(navegador, tmp_path):
    from panel.catalogo.prueba import preparar_sitio
    from tests.conftest import servir_carpetas
    sitio = tmp_path / "sitio"
    preparar_sitio(sitio, RAIZ, "cuenco", RAIZ / "tests" / "fixtures" / "mini.spz")
    carpeta = sitio / "piezas" / "cuenco"
    (carpeta / "index.html").write_text(renderizar_pieza(pieza(), URL), encoding="utf-8")
    import shutil
    est = RAIZ / "panel" / "catalogo" / "estatico"
    shutil.copy(est / "compartir.js", sitio / "compartir.js")
    shutil.copy(est / "estilos.css", sitio / "estilos.css")
    srv, url = servir_carpetas({"": sitio})
    try:
        p = navegador.new_page(viewport={"width": 1000, "height": 900})
        errores = []
        p.on("pageerror", lambda e: errores.append(str(e)))
        p.goto(f"{url}/piezas/cuenco/")
        p.wait_for_function("document.body.dataset.visor === 'listo'", timeout=30_000)
        assert not errores
        assert p.locator("img[alt='Código QR de Cuenco']").is_visible()
        assert p.locator("dl dt").count() == 4
    finally:
        srv.shutdown()
