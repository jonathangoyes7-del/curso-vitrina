"""Piezas de ejemplo: tres fotos de Unsplash (una por categoría) que entran por la cola.

Uso: `uv run python -m panel.ejemplos` (con el panel en marcha o no: solo crea las piezas
`pendiente`; el trabajador las procesa y quedan `para revisar`, nunca se publican solas).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

from panel.api import ingresar_foto
from panel.cola import Cola
from panel.config import Config

RUTA_JSON = Path(__file__).resolve().parent.parent / "ejemplos" / "ejemplos.json"


def descargar_http(url: str, destino: Path) -> Path:
    """Baja `url` con curl (viene con Windows 10/11): urllib recibe 401 de Unsplash tras la redirección."""
    try:
        subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "120",
                        "--output", str(destino), url],
                       check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        destino.unlink(missing_ok=True)
        detalle = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else "no se encontró curl"
        raise RuntimeError(f"No se pudo descargar {url}: {detalle}") from exc
    return destino


def cargar_ejemplos(cola: Cola, ruta_json: Path,
                    descargar: Callable[[str, Path], Path]) -> list[int]:
    """Descarga cada foto en un temporal dentro de `datos/` y la ingresa como ejemplo."""
    ejemplos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    tmp = cola.config.datos / f".ejemplos-{uuid.uuid4().hex}"
    tmp.mkdir(parents=True)
    ids: list[int] = []
    try:
        for n, e in enumerate(ejemplos):
            foto = descargar(e["url_descarga"], tmp / f"ejemplo{n}.jpg")
            ids.append(ingresar_foto(cola, foto, es_ejemplo=True,
                                     credito_autor=e["autor"], credito_url=e["enlace"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ids


def main() -> None:
    cola = Cola(Config.por_defecto())
    try:
        ids = cargar_ejemplos(cola, RUTA_JSON, descargar_http)
    finally:
        cola.cerrar()
    print(f"Piezas de ejemplo creadas (pendientes): {ids}")


if __name__ == "__main__":
    main()
