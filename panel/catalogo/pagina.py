"""Página de cada pieza: visor, ficha, QR, botón de compartir y código para incrustar (Tarea 17)."""
from __future__ import annotations

from panel.catalogo.componente import codigo_iframe, entorno_plantillas
from panel.catalogo.modelos import PiezaPublica
from panel.slug import url_pieza


def renderizar_pieza(pieza: PiezaPublica, url_publica: str) -> str:
    """HTML de `piezas/<slug>/index.html`. Rutas relativas (`raiz = "../../"`); solo `og:*` y el iframe son absolutos."""
    return entorno_plantillas().get_template("pieza.html").render(
        pieza=pieza, raiz="../../",
        url_pieza=url_pieza(url_publica, pieza.slug),
        url_portada=f"{url_publica}piezas/{pieza.slug}/portada.jpg",
        codigo_iframe=codigo_iframe(pieza, url_publica))
