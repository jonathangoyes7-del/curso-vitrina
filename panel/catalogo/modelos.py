"""Modelos del sitio público."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from panel.ficha import Ficha


@dataclass(frozen=True)
class PiezaPublica:
    slug: str
    ficha: Ficha
    es_ejemplo: bool
    credito_autor: str | None
    credito_url: str | None
    carpeta: Path   # la carpeta vigente/
