"""Grabación del Reel: Chromium (Playwright) pinta el visor cuadro a cuadro y ffmpeg lo convierte en MP4 vertical."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable

ANCHO, ALTO = 1080, 1920
ARGS_CHROMIUM = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]  # los mismos que tests/conftest.py
ESPERA_VISOR_MS = 60_000

log = logging.getLogger(__name__)


def _registrar_gpu(pagina) -> None:
    render = pagina.evaluate("""() => {
        const gl = document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl');
        if (!gl) return '(sin WebGL)';
        const ext = gl.getExtension('WEBGL_debug_renderer_info');
        return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : '(desconocido)';
    }""")
    log.info("UNMASKED_RENDERER_WEBGL: %s", render)
    if "NVIDIA" not in render:
        log.warning("El Reel se está pintando sin la GPU NVIDIA (%s): será lento.", render)


def grabar_reel(url_pagina: str, destino: Path, *, segundos: int = 12, fps: int = 30,
                informar: Callable[[float], None] = lambda f: None) -> Path:
    """Graba una vuelta completa de la pieza en `destino` (MP4 h264 de 1080×1920) y lo devuelve.

    Escribe primero en un archivo temporal: si algo falla, no queda un .mp4 a medias.
    """
    from playwright.sync_api import sync_playwright

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.stem + ".tmp" + destino.suffix)
    total = segundos * fps
    ffmpeg = None
    try:
        with sync_playwright() as pw:
            navegador = pw.chromium.launch(args=ARGS_CHROMIUM)
            try:
                pagina = navegador.new_page(viewport={"width": ANCHO, "height": ALTO})
                pagina.goto(url_pagina)
                _registrar_gpu(pagina)
                pagina.wait_for_function("['listo', 'error'].includes(document.body.dataset.visor)",
                                         timeout=ESPERA_VISOR_MS)
                if pagina.evaluate("document.body.dataset.visor") == "error":
                    raise RuntimeError(f"El visor no pudo cargar la pieza ({url_pagina})")
                # Calentamiento: el primer render de Spark deja los gaussianos sin ordenar y el cuadro 0 salía vacío.
                for _ in range(3):
                    pagina.evaluate("([i, total]) => window.visor.irACuadro(i, total)", [0, total])
                ffmpeg = subprocess.Popen(
                    ["ffmpeg", "-y", "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(temporal)],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for i in range(total):
                    pagina.evaluate("([i, total]) => window.visor.irACuadro(i, total)", [i, total])
                    ffmpeg.stdin.write(pagina.screenshot(type="png"))
                    informar((i + 1) / total)
            finally:
                navegador.close()
        ffmpeg.stdin.close()
        if ffmpeg.wait() != 0:
            raise RuntimeError("ffmpeg falló al codificar el Reel")
        temporal.replace(destino)
        return destino
    except BaseException:
        if ffmpeg is not None:
            ffmpeg.kill()
            ffmpeg.wait()
        temporal.unlink(missing_ok=True)
        raise
