"""Generador del sitio público (Tarea 18): galería, páginas de pieza, embed y librerías.

Regenerar `sitio/` con las piezas aprobadas: `uv run python -m panel.catalogo.generador`.
"""
from __future__ import annotations

import gzip
import re
import shutil
import tempfile
from pathlib import Path

from panel.catalogo.componente import entorno_plantillas, renderizar_embed
from panel.catalogo.creditos import renderizar_creditos
from panel.catalogo.modelos import PiezaPublica
from panel.catalogo.pagina import renderizar_pieza
from panel.catalogo.rutas import rutas_absolutas_locales
from panel.cola import Cola
from panel.ficha import CATEGORIAS
from panel.qr import generar_qr
from panel.slug import url_pieza

ESTATICO = Path(__file__).parent / "estatico"
MARCA = ".vitrina-sitio"
LIMITE_VENDOR = int(1.6 * 1024 * 1024)   # Three y Spark, con gzip: tope aparte del de cada página
EXTENSIONES = {".html", ".css", ".js", ".spz", ".jpg", ".svg"}
ARCHIVOS_SUELTOS = {".nojekyll", MARCA, "LICENSE"}
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# (origen dentro de node_modules, destino dentro de sitio/vendor)
_VENDOR = (
    ("three/build/three.module.js", "three/three.module.js"),
    ("three/build/three.core.js", "three/three.core.js"),
    ("three/examples/jsm/controls/OrbitControls.js", "three/addons/controls/OrbitControls.js"),
    ("three/examples/jsm/postprocessing/Pass.js", "three/addons/postprocessing/Pass.js"),
    ("three/LICENSE", "three/LICENSE"),
    ("@sparkjsdev/spark/dist/spark.module.js", "spark/spark.module.js"),
    ("@sparkjsdev/spark/LICENSE", "spark/LICENSE"),
)


def publicas_desde_cola(cola: Cola) -> list[PiezaPublica]:
    """Las piezas que van al sitio: la versión aprobada (`ficha_vigente`, `vigente/`), nunca el borrador."""
    return [PiezaPublica(slug=p.slug, ficha=p.ficha_vigente, es_ejemplo=p.es_ejemplo,
                         credito_autor=p.credito_autor, credito_url=p.credito_url,
                         carpeta=cola.carpeta_vigente(p.id))
            for p in cola.piezas_para_sitio() if p.slug and p.ficha_vigente]


def renderizar_galeria(piezas: list[PiezaPublica]) -> str:
    return entorno_plantillas().get_template("galeria.html").render(
        piezas=piezas, categorias=CATEGORIAS, raiz="",
        creditos=[p for p in piezas if p.es_ejemplo and p.credito_autor])


def _copiar(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origen, destino)


def generar_sitio(piezas: list[PiezaPublica], destino: Path, raiz_proyecto: Path, url_publica: str) -> None:
    destino = Path(destino)
    if destino.name != "sitio":
        raise ValueError(f"Me niego a vaciar «{destino}»: la carpeta debe llamarse «sitio».")
    if destino.exists() and not (destino / MARCA).is_file():
        raise ValueError(f"Me niego a vaciar «{destino}»: no es un sitio generado por Vitrina (falta {MARCA}).")
    slugs = [p.slug for p in piezas]
    for s in slugs:
        if not _SLUG.fullmatch(s):
            raise ValueError(f"slug no válido: {s!r}")
    if len(set(slugs)) != len(slugs):
        raise ValueError("Hay dos piezas con el mismo slug.")
    for p in piezas:
        for f in ("pieza.spz", "portada.jpg"):
            if not (p.carpeta / f).is_file():
                raise ValueError(f"A la pieza «{p.slug}» le falta {f} en {p.carpeta}.")

    # Se arma aparte y se cambia al final: si algo falla, el sitio anterior queda intacto.
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = Path(tempfile.mkdtemp(prefix="sitio-", dir=destino.parent))
    try:
        (temporal / MARCA).write_text("Generado por Vitrina; se vacía en cada generación.\n", encoding="utf-8")
        (temporal / ".nojekyll").write_text("", encoding="utf-8")
        (temporal / "index.html").write_text(renderizar_galeria(piezas), encoding="utf-8")
        (temporal / "creditos").mkdir()
        (temporal / "creditos" / "index.html").write_text(renderizar_creditos(piezas), encoding="utf-8")
        for nombre in ("estilos.css", "compartir.js", "galeria.js"):
            _copiar(ESTATICO / nombre, temporal / nombre)
        _copiar(ESTATICO / "vitrina-pieza.js", temporal / "componente" / "vitrina-pieza.js")
        _copiar(raiz_proyecto / "visor" / "visor.js", temporal / "visor" / "visor.js")
        for origen, rel in _VENDOR:
            _copiar(raiz_proyecto / "node_modules" / origen, temporal / "vendor" / rel)
        for p in piezas:
            carpeta = temporal / "piezas" / p.slug
            carpeta.mkdir(parents=True)
            (carpeta / "index.html").write_text(renderizar_pieza(p, url_publica), encoding="utf-8")
            _copiar(p.carpeta / "pieza.spz", carpeta / "pieza.spz")
            _copiar(p.carpeta / "portada.jpg", carpeta / "portada.jpg")
            generar_qr(url_pieza(url_publica, p.slug), carpeta / "qr.svg")   # siempre al día con la URL de config
            (temporal / "embed" / p.slug).mkdir(parents=True)
            (temporal / "embed" / p.slug / "index.html").write_text(renderizar_embed(p), encoding="utf-8")
        if destino.exists():
            shutil.rmtree(destino)
        temporal.rename(destino)
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise


def _gzip(ruta: Path) -> int:
    return len(gzip.compress(ruta.read_bytes(), 6))


def verificar_sitio(destino: Path, limite_spz: int, limite_pagina: int) -> list[str]:
    """Problemas del sitio generado, en castellano (lista vacía = todo bien)."""
    from PIL import Image
    destino = Path(destino)
    problemas: list[str] = []

    def rel(r: Path) -> str:
        return r.relative_to(destino).as_posix()

    for r in sorted(destino.rglob("*")):
        if not r.is_file():
            continue
        sufijo = r.suffix.lower()
        if r.name not in ARCHIVOS_SUELTOS and sufijo not in EXTENSIONES:
            problemas.append(f"Archivo no permitido en el sitio: {rel(r)}")
        if sufijo == ".jpg":
            try:
                with Image.open(r) as im:
                    if len(im.getexif()) or "exif" in im.info:
                        problemas.append(f"La imagen {rel(r)} lleva datos EXIF (podrían incluir la ubicación).")
            except OSError:
                problemas.append(f"La imagen {rel(r)} no se puede abrir.")
        if sufijo == ".spz" and r.stat().st_size > limite_spz:
            problemas.append(f"El splat {rel(r)} pesa {r.stat().st_size / 1048576:.1f} MB y el límite es "
                             f"{limite_spz / 1048576:.0f} MB.")
        if sufijo == ".html":
            for ruta in rutas_absolutas_locales(r.read_text(encoding="utf-8")):
                problemas.append(f"{rel(r)} usa la ruta absoluta «{ruta}» (en GitHub Pages debe ser relativa).")
    comunes = sum(_gzip(destino / f) for f in ("estilos.css", "compartir.js", "visor/visor.js")
                  if (destino / f).is_file())
    for pagina in sorted((destino / "piezas").glob("*/index.html")):
        propios = (pagina, pagina.parent / "portada.jpg", pagina.parent / "qr.svg")
        peso = comunes + sum(_gzip(f) for f in propios if f.is_file())
        if peso >= limite_pagina:
            problemas.append(f"La página de {pagina.parent.name} pesa {peso / 1024:.0f} KB con gzip y el límite es "
                             f"{limite_pagina / 1024:.0f} KB (sin contar Three ni Spark).")
    if (destino / "vendor").is_dir():
        vendor = sum(_gzip(f) for f in (destino / "vendor").rglob("*") if f.is_file())
        if vendor > LIMITE_VENDOR:
            problemas.append(f"Three y Spark pesan {vendor / 1048576:.2f} MB con gzip y el tope es "
                             f"{LIMITE_VENDOR / 1048576:.1f} MB.")
    return problemas


def main() -> int:
    from panel.config import Config
    config = Config.por_defecto()
    cola = Cola(config)
    try:
        piezas = publicas_desde_cola(cola)
    finally:
        cola.cerrar()
    generar_sitio(piezas, config.sitio, config.raiz, config.url_publica)
    print(f"Sitio generado en {config.sitio} con {len(piezas)} pieza(s): "
          f"{', '.join(p.slug for p in piezas) or 'ninguna'}")
    problemas = verificar_sitio(config.sitio, config.limite_spz, config.limite_pagina)
    for p in problemas:
        print(f"PROBLEMA: {p}")
    print("Verificación: sin problemas." if not problemas else f"Verificación: {len(problemas)} problema(s).")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
