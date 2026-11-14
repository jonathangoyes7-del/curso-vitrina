"""Revisor y limpieza de fotos de las piezas."""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

FORMATOS_VALIDOS = {"JPEG", "PNG", "WEBP", "HEIF"}
LADO_MENOR_MINIMO = 768
LADO_ANALISIS = 1024
# Calibrado con las 5 fotos de la tienda, ceramica.jpg y la foto del pico:
# nítidas >= 69,3 (la más baja es camion_madera); con GaussianBlur(6) <= 4,6;
# con GaussianBlur(4) <= 16,9. 20 deja margen a ambos lados.
UMBRAL_NITIDEZ = 20.0
LADO_PORTADA = 1200
# Fotos pequeñas del panel: la lista (tarjetas) y la ficha (junto al formulario, 26 rem a 2x).
MINIATURAS = {"lista.jpg": 360, "ficha.jpg": 800}
CALIDAD_MINIATURA = 78


@dataclass
class RevisionFoto:
    aceptada: bool
    problemas: list[str] = field(default_factory=list)


def _abrir(ruta: Path) -> Image.Image:
    """Abre y decodifica la foto con la orientación EXIF ya aplicada."""
    im = Image.open(ruta)
    if im.format not in FORMATOS_VALIDOS:
        im.close()
        raise ValueError(f"formato {im.format}")
    im.load()
    return ImageOps.exif_transpose(im)


def medir_nitidez(im: Image.Image) -> float:
    """Varianza de FIND_EDGES sobre la imagen en gris con el lado mayor a 1024 px."""
    gris = ImageOps.exif_transpose(im).convert("L")
    gris.thumbnail((LADO_ANALISIS, LADO_ANALISIS), Image.LANCZOS)
    # Pillow no filtra el marco de 1 px (conserva el gris original); se descarta.
    bordes = np.asarray(gris.filter(ImageFilter.FIND_EDGES), dtype=np.float64)[1:-1, 1:-1]
    return float(bordes.var())


def revisar_foto(ruta: Path) -> RevisionFoto:
    try:
        im = _abrir(Path(ruta))
    except Exception:
        return RevisionFoto(False, ["No se pudo abrir la foto. Usa una imagen JPEG, PNG, WEBP o HEIC."])
    with im:
        problemas = []
        if min(im.size) < LADO_MENOR_MINIMO:
            problemas.append(
                f"El lado menor mide {min(im.size)} px; debe medir al menos {LADO_MENOR_MINIMO} px."
            )
        if medir_nitidez(im) < UMBRAL_NITIDEZ:
            problemas.append("La foto está borrosa. Enfoca la pieza y vuelve a tomarla.")
    return RevisionFoto(not problemas, problemas)


def limpiar_foto(origen: Path, destino: Path) -> Path:
    """JPEG q92 sin EXIF ni XMP; la orientación se aplica antes de descartar los metadatos."""
    with Image.open(origen) as im:
        limpia = ImageOps.exif_transpose(im).convert("RGB")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    limpia.save(destino, format="JPEG", quality=92)
    return destino


def crear_portada(foto_limpia: Path, destino: Path) -> Path:
    """JPEG de 1200 px en el lado mayor, calidad 82, sin metadatos."""
    with Image.open(foto_limpia) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        escala = LADO_PORTADA / max(im.size)
        nuevo = (round(im.width * escala), round(im.height * escala))
        portada = im.resize(nuevo, Image.LANCZOS)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    portada.save(destino, format="JPEG", quality=82)
    return destino


def crear_miniaturas(foto: Path, carpeta: Path) -> list[Path]:
    """`lista.jpg` (360 px) y `ficha.jpg` (800 px) en el lado mayor: JPEG progresivo sin metadatos.

    Nunca amplía: si la foto es más pequeña que el tamaño pedido, conserva el suyo.
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    with Image.open(foto) as im:
        base = ImageOps.exif_transpose(im).convert("RGB")
    creadas = []
    for nombre, lado in MINIATURAS.items():
        mini = base.copy()
        mini.thumbnail((lado, lado), Image.LANCZOS)
        destino = carpeta / nombre
        mini.save(destino, format="JPEG", quality=CALIDAD_MINIATURA, optimize=True, progressive=True)
        creadas.append(destino)
    return creadas


def completar_miniaturas(carpeta_piezas: Path) -> int:
    """Crea las miniaturas que falten en `borrador/` y `vigente/` de cada pieza; devuelve cuántas carpetas tocó.

    Parte de `foto.jpg` (o de `portada.jpg` si no hay). Nunca toca la foto original ni
    reescribe miniaturas que ya existen. Se ignoran las carpetas que no son un id numérico.
    """
    tocadas = 0
    carpeta_piezas = Path(carpeta_piezas)
    if not carpeta_piezas.is_dir():
        return 0
    for pieza in sorted(carpeta_piezas.iterdir()):
        if not (pieza.is_dir() and pieza.name.isdigit()):
            continue
        for version in ("borrador", "vigente"):
            carpeta = pieza / version
            if all((carpeta / n).is_file() for n in MINIATURAS):
                continue
            origen = next((carpeta / n for n in ("foto.jpg", "portada.jpg") if (carpeta / n).is_file()), None)
            if origen is None:
                continue
            crear_miniaturas(origen, carpeta)
            tocadas += 1
    return tocadas
