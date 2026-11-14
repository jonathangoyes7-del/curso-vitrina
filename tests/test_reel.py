"""Tests de la grabación del Reel (Chromium + ffmpeg reales)."""
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from PIL import Image

from panel.reel import grabar_reel as _grabar_reel

pytestmark = pytest.mark.navegador


def grabar_reel(*args, **kwargs):
    """Como en producción, en un hilo aparte: el fixture `navegador` ya tiene un Playwright vivo en el hilo principal."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(_grabar_reel, *args, **kwargs).result()


def ffprobe(mp4):
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_streams", "-of", "json", str(mp4)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(salida)["streams"][0]


def cuadro(mp4, n):
    """Cuadro n (empezando en 0) del MP4 como matriz de grises."""
    png = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"select=eq(n\\,{n})", "-vframes", "1",
         "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True).stdout
    return np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype="float64")


def test_reel_formato(tmp_path, servidor_estatico):
    avances = []
    mp4 = grabar_reel(f"{servidor_estatico}/visor/reel.html?splat=/fixtures/mini.spz&nombre=Prueba",
                      tmp_path / "r.mp4", segundos=2, informar=avances.append)
    info = ffprobe(mp4)
    assert (info["width"], info["height"], info["codec_name"], info["pix_fmt"]) == (1080, 1920, "h264", "yuv420p")
    assert int(info["nb_frames"]) == 60 and avances[-1] >= 0.98


def test_reel_vuelta_completa(tmp_path, servidor_estatico):
    mp4 = grabar_reel(f"{servidor_estatico}/visor/reel.html?splat=/fixtures/mini.spz&nombre=Prueba",
                      tmp_path / "r.mp4", segundos=2)
    primero, medio, ultimo = cuadro(mp4, 0), cuadro(mp4, 30), cuadro(mp4, 59)
    d = lambda a, b: float(np.abs(a - b).mean())  # noqa: E731
    assert d(primero, ultimo) < d(primero, medio)   # el último cuadro vuelve casi al primero; el del medio es otro
    assert d(primero, medio) > 0.1


def test_reel_splat_roto(tmp_path, servidor_estatico):
    destino = tmp_path / "r.mp4"
    with pytest.raises(RuntimeError):
        grabar_reel(f"{servidor_estatico}/visor/reel.html?splat=/fixtures/no_existe.spz&nombre=X",
                    destino, segundos=1)
    assert not destino.exists() and not list(tmp_path.glob("*.mp4*"))


def test_reel_ningun_cuadro_vacio(tmp_path, servidor_estatico):
    """El primer cuadro ya lleva la pieza (Spark necesita un primer render para ordenar los gaussianos)."""
    mp4 = grabar_reel(f"{servidor_estatico}/visor/reel.html?splat=/fixtures/mini.spz&nombre=Prueba",
                      tmp_path / "r.mp4", segundos=1)
    centro = cuadro(mp4, 0)[500:1100]   # franja de la pieza, sin el nombre
    assert centro.std() > 3
