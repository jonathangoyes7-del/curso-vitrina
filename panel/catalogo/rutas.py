"""Comprobación de rutas del sitio (subruta de GitHub Pages: deben ser relativas)."""
from __future__ import annotations

import re

_ATRIBUTO = re.compile(r"""\b(?:src|href)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)


def rutas_absolutas_locales(html: str) -> list[str]:
    """Los `src` y `href` que empiezan por `/` sin ser `//`."""
    valores = (a or b for a, b in _ATRIBUTO.findall(html))
    return [v for v in valores if v.startswith("/") and not v.startswith("//")]
