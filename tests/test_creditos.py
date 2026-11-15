"""Página de créditos y licencias (Tarea 20 bis): modelos, librerías y fotos de Unsplash."""
from pathlib import Path

from panel.catalogo.creditos import LIBRERIAS_CONSTRUCCION, LIBRERIAS_SITIO, MODELOS, renderizar_creditos
from panel.catalogo.modelos import PiezaPublica
from panel.catalogo.rutas import rutas_absolutas_locales
from panel.ficha import Ficha


def pieza(slug="cuenco", nombre="Cuenco", **extra):
    datos = dict(es_ejemplo=False, credito_autor=None, credito_url=None)
    datos.update(extra)
    return PiezaPublica(slug=slug, ficha=Ficha(nombre, "Gres y esmalte", "Cerámica", "Lavar a mano."),
                        carpeta=Path("vigente"), **datos)


def test_creditos_lista_modelos_librerias_y_fotos():
    html = renderizar_creditos([pieza(es_ejemplo=True, credito_autor="Ana Pérez",
                                      credito_url="https://unsplash.com/@ana")])
    for texto in ["Idol", "DINOv3", "FLUX.2-klein-4B", "Gemma", "Three.js", "Spark", "PyTorch", "FastAPI", "Jinja2"]:
        assert texto in html
    assert "Built with DINOv3" in html and 'href="https://unsplash.com/@ana"' in html and "Ana Pérez" in html
    assert 'href="https://unsplash.com/license"' in html and not rutas_absolutas_locales(html)
    assert 'href="../"' in html


def test_creditos_sin_ejemplos_omite_fotos():
    html = renderizar_creditos([pieza()])
    assert "Fotos de ejemplo" not in html and "Modelos" in html and "Librerías" in html


def test_creditos_escapa_autor():
    html = renderizar_creditos([pieza(es_ejemplo=True, credito_autor="<b>X</b>",
                                      credito_url="https://unsplash.com/@x")])
    assert "<b>" not in html and "&lt;b&gt;X" in html


def test_modelos_con_licencia_comercial():
    assert MODELOS
    assert all("no comercial" not in m.licencia.lower() and m.url_licencia.startswith("https://") for m in MODELOS)


def test_librerias_con_licencia_y_enlace():
    todas = LIBRERIAS_SITIO + LIBRERIAS_CONSTRUCCION
    assert {c.nombre.split()[0] for c in LIBRERIAS_SITIO} == {"Three.js", "Spark"}
    assert all(c.licencia and c.url_licencia.startswith("https://") for c in todas)
