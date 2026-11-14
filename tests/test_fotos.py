from pathlib import Path

import pytest
from PIL import Image, ImageFilter

from panel.fotos import completar_miniaturas, crear_miniaturas, crear_portada, limpiar_foto, revisar_foto

FIXTURES = Path(__file__).parent / "fixtures" / "fotos"


def fixture(nombre: str) -> Path:
    return FIXTURES / nombre


def img(tmp_path, ancho, alto, nombre="p.jpg"):
    """Foto con bordes nítidos (tablero), para que solo falle por tamaño."""
    im = Image.new("RGB", (ancho, alto), "white")
    px = im.load()
    for y in range(alto):
        for x in range(ancho):
            if (x // 8 + y // 8) % 2:
                px[x, y] = (30, 30, 30)
    ruta = tmp_path / nombre
    im.save(ruta, quality=95)
    return ruta


def jpeg_con_gps(tmp_path):
    im = Image.new("RGB", (800, 800), "gray")
    exif = Image.Exif()
    exif[0x010F] = "Marca"
    exif.get_ifd(0x8825).update({1: "N", 2: (4.0, 36.0, 0.0), 3: "W", 4: (74.0, 5.0, 0.0)})
    ruta = tmp_path / "gps.jpg"
    im.save(ruta, exif=exif, xmp=b"<x:xmpmeta/>")
    return ruta


def jpeg_apaisado_con_orientacion(tmp_path, ancho, alto, orientacion):
    im = Image.new("RGB", (ancho, alto), "gray")
    exif = Image.Exif()
    exif[0x0112] = orientacion
    ruta = tmp_path / "giro.jpg"
    im.save(ruta, exif=exif)
    return ruta


def desenfocada(origen, tmp_path):
    with Image.open(origen) as im:
        ruta = tmp_path / "borrosa.jpg"
        im.convert("RGB").filter(ImageFilter.GaussianBlur(6)).save(ruta, quality=92)
    return ruta


def texto(tmp_path, nombre):
    ruta = tmp_path / nombre
    ruta.write_text("esto no es una imagen")
    return ruta


def heic_desde(origen, tmp_path):
    from pillow_heif import register_heif_opener
    register_heif_opener()
    ruta = tmp_path / "foto.heic"
    with Image.open(origen) as im:
        im.convert("RGB").save(ruta, format="HEIF")
    return ruta


def test_limpiar_quita_gps(tmp_path):
    origen = jpeg_con_gps(tmp_path)
    with Image.open(origen) as im:   # el origen sí lleva metadatos
        assert im.getexif().get_ifd(0x8825) and "xmp" in im.info
    limpia = limpiar_foto(origen, tmp_path / "f.jpg")
    with Image.open(limpia) as im:
        assert not im.getexif() and "exif" not in im.info and "xmp" not in im.info


def test_limpiar_respeta_orientacion(tmp_path):
    origen = jpeg_apaisado_con_orientacion(tmp_path, 1600, 1200, orientacion=6)
    with Image.open(limpiar_foto(origen, tmp_path / "f.jpg")) as im:
        assert im.size == (1200, 1600)


def test_rechaza_pequena(tmp_path):
    assert "lado" in " ".join(revisar_foto(img(tmp_path, 600, 800)).problemas)


def test_rechaza_borrosa(tmp_path):
    assert not revisar_foto(desenfocada(fixture("ceramica.jpg"), tmp_path)).aceptada


def test_acepta_nitida():
    assert revisar_foto(fixture("ceramica.jpg")).aceptada


def test_rechaza_no_imagen(tmp_path):
    assert not revisar_foto(texto(tmp_path, "x.jpg")).aceptada


def test_acepta_heic(tmp_path):
    assert revisar_foto(heic_desde(fixture("ceramica.jpg"), tmp_path)).aceptada


def test_portada_tamano(tmp_path):
    with Image.open(crear_portada(fixture("ceramica.jpg"), tmp_path / "p.jpg")) as im:
        assert max(im.size) == 1200 and not im.getexif()


def test_miniaturas_dos_tamanos_ligeras_y_sin_metadatos(tmp_path):
    lista, ficha = crear_miniaturas(fixture("ceramica.jpg"), tmp_path)
    assert (lista.name, ficha.name) == ("lista.jpg", "ficha.jpg")
    with Image.open(lista) as a, Image.open(ficha) as b:
        assert max(a.size) <= 360 and max(b.size) <= 800
        assert max(a.size) < max(b.size) and not a.getexif() and not b.getexif()
    assert lista.stat().st_size < ficha.stat().st_size < crear_portada(
        fixture("ceramica.jpg"), tmp_path / "p.jpg").stat().st_size


def test_miniaturas_no_amplian(tmp_path):
    Image.new("RGB", (200, 100), (10, 20, 30)).save(tmp_path / "chica.jpg")
    for ruta in crear_miniaturas(tmp_path / "chica.jpg", tmp_path / "m"):
        with Image.open(ruta) as im:
            assert im.size == (200, 100)


def test_completar_miniaturas_en_piezas_existentes(tmp_path):
    for nombre, version in (("1", "borrador"), ("1", "vigente"), ("2", "borrador")):
        carpeta = tmp_path / nombre / version
        carpeta.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (900, 600), (1, 2, 3)).save(carpeta / "foto.jpg")
    (tmp_path / "abc" / "borrador").mkdir(parents=True)  # no es un id: se ignora
    assert completar_miniaturas(tmp_path) == 3
    assert (tmp_path / "1" / "vigente" / "ficha.jpg").is_file()
    assert (tmp_path / "2" / "borrador" / "lista.jpg").is_file()
    assert not (tmp_path / "abc" / "borrador" / "lista.jpg").exists()
    assert completar_miniaturas(tmp_path) == 0  # idempotente
