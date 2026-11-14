"""Código QR de cada pieza, en SVG y PNG, hacia la página que tendrá al publicarse (Tarea 13)."""
from __future__ import annotations

from pathlib import Path

import segno

from panel.cola import Cola, Estado
from panel.slug import asegurar_slug, url_pieza

OSCURO, CLARO = "#2E2D2B", "#F5F1E8"          # --grafito y --papel
ESTADOS_CON_QR = {Estado.PARA_REVISAR, Estado.APROBADA, Estado.PUBLICADA, Estado.DESPUBLICADA}


def generar_qr(url: str, destino: Path) -> Path:
    """SVG vectorial (para imprimir a cualquier tamaño)."""
    segno.make(url, error="m").save(str(destino), kind="svg", scale=8, border=4, dark=OSCURO, light=CLARO)
    return destino


def generar_qr_png(url: str, destino: Path) -> Path:
    """PNG de unos 900 px de lado (cada módulo mide 20 px) para quien no abre SVG."""
    segno.make(url, error="m").save(str(destino), kind="png", scale=20, border=4, dark=OSCURO, light=CLARO)
    return destino


def refrescar_qr(cola: Cola, id: int) -> str:
    """Asegura el slug de la pieza y deja `qr.svg` y `qr.png` en su borrador. Devuelve la URL."""
    url = url_pieza(cola.config.url_publica, asegurar_slug(cola, id))
    borrador = cola.carpeta_borrador(id)
    borrador.mkdir(parents=True, exist_ok=True)
    generar_qr(url, borrador / "qr.svg")
    generar_qr_png(url, borrador / "qr.png")
    return url


def completar_qr(cola: Cola) -> int:
    """Da QR a las piezas que ya existían (revisión, aprobadas, publicadas); salta las que no están listas."""
    hechas = 0
    for p in sorted(cola.listar(), key=lambda p: p.id):
        if p.estado in ESTADOS_CON_QR:
            refrescar_qr(cola, p.id)
            hechas += 1
    return hechas
