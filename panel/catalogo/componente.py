"""Código para incrustar una pieza en otra web: <iframe> y etiqueta <vitrina-pieza>."""
from __future__ import annotations

import re
from pathlib import Path

import jinja2
from markupsafe import escape

from panel.catalogo.modelos import PiezaPublica

CARPETA = Path(__file__).parent
RUTA_COMPONENTE = CARPETA / "estatico" / "vitrina-pieza.js"
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def entorno_plantillas() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(CARPETA / "plantillas"),
        autoescape=True, undefined=jinja2.StrictUndefined)


def codigo_iframe(pieza: PiezaPublica, url_publica: str) -> str:
    return (f'<iframe src="{url_publica}embed/{pieza.slug}/" title="{escape(pieza.ficha.nombre)} en 3D" '
            'width="100%" height="480" style="border:0" loading="lazy" allow="fullscreen"></iframe>')


def codigo_etiqueta(slug: str, url_publica: str) -> str:
    """La etiqueta `<vitrina-pieza>` en una sola línea: carga el componente y lo usa."""
    if not _SLUG.fullmatch(slug):
        raise ValueError(f"slug no válido: {slug!r}")
    return (f'<script type="module" src="{url_publica}componente/vitrina-pieza.js"></script>'
            f'<vitrina-pieza pieza="{slug}"></vitrina-pieza>')


def renderizar_embed(pieza: PiezaPublica) -> str:
    return entorno_plantillas().get_template("embed.html").render(
        pieza=pieza, raiz="../../", url_splat=f"../../piezas/{pieza.slug}/pieza.spz")
