"""Sitio mínimo de prueba para el componente de incrustación.

Reúne lo que luego publicará `generar_sitio` (Tarea 18): el componente, la página embed de una
pieza, su splat, el visor y las librerías. Lo usan los tests y `herramientas/probar_etiqueta.py`.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from panel.catalogo.componente import RUTA_COMPONENTE, renderizar_embed
from panel.catalogo.modelos import PiezaPublica
from panel.ficha import Ficha

_THREE = (("build/three.module.js", "three.module.js"), ("build/three.core.js", "three.core.js"),
          ("examples/jsm/controls/OrbitControls.js", "addons/controls/OrbitControls.js"),
          ("examples/jsm/postprocessing/Pass.js", "addons/postprocessing/Pass.js"))


def pieza_de_prueba(slug: str, nombre: str = "Pieza de prueba") -> PiezaPublica:
    return PiezaPublica(slug=slug, ficha=Ficha(nombre, "Gres", "Cerámica", "Lavar a mano."),
                        es_ejemplo=False, credito_autor=None, credito_url=None, carpeta=Path("vigente"))


def preparar_sitio(destino: Path, raiz: Path, slug: str, splat: Path) -> None:
    """Escribe en `destino` un sitio publicado con una sola pieza (`destino` no debe existir)."""
    (destino / "componente").mkdir(parents=True)
    shutil.copy(RUTA_COMPONENTE, destino / "componente" / "vitrina-pieza.js")
    (destino / "embed" / slug).mkdir(parents=True)
    (destino / "embed" / slug / "index.html").write_text(
        renderizar_embed(pieza_de_prueba(slug)), encoding="utf-8")
    (destino / "piezas" / slug).mkdir(parents=True)
    shutil.copy(splat, destino / "piezas" / slug / "pieza.spz")
    (destino / "visor").mkdir()
    shutil.copy(raiz / "visor" / "visor.js", destino / "visor" / "visor.js")
    for origen, rel in _THREE:
        objetivo = destino / "vendor" / "three" / rel
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(raiz / "node_modules" / "three" / origen, objetivo)
    (destino / "vendor" / "spark").mkdir(parents=True)
    shutil.copy(raiz / "node_modules" / "@sparkjsdev" / "spark" / "dist" / "spark.module.js",
                destino / "vendor" / "spark" / "spark.module.js")
