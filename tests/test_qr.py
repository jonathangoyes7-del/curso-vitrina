import io
import sqlite3

import segno
from fastapi.testclient import TestClient
from PIL import Image

from panel.api import crear_app
from panel.cola import Cola
from panel.ficha import Ficha
from panel.qr import completar_qr, generar_qr, generar_qr_png, refrescar_qr
from panel.slug import asegurar_slug, crear_slug, url_pieza
from tests.test_cola import EtapaFalsa, ficha, procesar_con_etapas_falsas

URL_BASE = "https://jonathangoyes7-del.github.io/curso-vitrina/"


def pieza_para_revisar(config, nombre="Cuenco"):
    c = Cola(config)
    i = c.crear_pieza()
    procesar_con_etapas_falsas(c, i)
    c.guardar_ficha_borrador(i, ficha(nombre))
    return c, i


def test_crear_slug():
    assert crear_slug("Cuenco de Gres ñandú", set()) == "cuenco-de-gres-nandu"
    assert crear_slug("Cuenco", {"cuenco"}) == "cuenco-2"
    assert crear_slug("Cuenco", {"cuenco", "cuenco-2"}) == "cuenco-3"
    assert crear_slug("¡¡!!", set()) == "pieza"
    assert crear_slug("  Bolso -- de   cuero  ", set()) == "bolso-de-cuero"
    assert len(crear_slug("a" * 100, set())) == 60


def test_slug_fijo_tras_aprobar(config_tmp):
    c, i = pieza_para_revisar(config_tmp, "Cuenco")
    assert asegurar_slug(c, i) == "cuenco"
    c.aprobar(i)
    c.editar_ficha(i, ficha("Jarra"))
    assert asegurar_slug(c, i) == "cuenco"


def test_slug_cambia_antes_de_aprobar(config_tmp):
    c, i = pieza_para_revisar(config_tmp, "Cuenco")
    assert asegurar_slug(c, i) == "cuenco"
    c.editar_ficha(i, ficha("Jarra"))
    assert asegurar_slug(c, i) == "jarra"
    assert c.obtener(i).slug == "jarra"


def test_slug_no_choca_con_otras_piezas(config_tmp):
    c, i = pieza_para_revisar(config_tmp, "Cuenco")
    j = c.crear_pieza()
    procesar_con_etapas_falsas(c, j)
    c.guardar_ficha_borrador(j, ficha("Cuenco"))
    assert asegurar_slug(c, i) == "cuenco"
    assert asegurar_slug(c, j) == "cuenco-2"
    assert asegurar_slug(c, i) == "cuenco"      # recalcular no se choca con su propio slug


def test_aprobada_sin_slug_lo_recibe_de_la_ficha_aprobada(config_tmp):
    # Piezas aprobadas antes de que existiera el slug: slug_fijo=1 pero slug NULL.
    c, i = pieza_para_revisar(config_tmp, "Bolso de cuero")
    c.aprobar(i)
    assert c.obtener(i).slug is None
    c.editar_ficha(i, ficha("Otro nombre"))     # el borrador cambia, lo aprobado no
    assert asegurar_slug(c, i) == "bolso-de-cuero"
    assert asegurar_slug(c, i) == "bolso-de-cuero"


def test_qr(tmp_path):
    url = url_pieza(URL_BASE, "cuenco")
    assert url == "https://jonathangoyes7-del.github.io/curso-vitrina/piezas/cuenco/"
    svg = generar_qr(url, tmp_path / "qr.svg").read_text()
    esperado = io.BytesIO()
    segno.make(url, error="m").save(esperado, kind="svg", scale=8, border=4, dark="#2E2D2B", light="#F5F1E8")
    assert svg == esperado.getvalue().decode() and "#2e2d2b" in svg.lower()


def test_qr_png_se_decodifica_a_la_misma_matriz(tmp_path):
    url = url_pieza(URL_BASE, "cuenco")
    ruta = generar_qr_png(url, tmp_path / "qr.png")
    img = Image.open(ruta).convert("RGB")
    assert img.width == img.height and img.width >= 600           # tamaño para imprimir
    assert img.getpixel((0, 0)) == (0xF5, 0xF1, 0xE8)            # fondo papel, margen de 4 módulos
    matriz = segno.make(url, error="m").matrix
    modulo = img.width // (len(matriz) + 8)
    centro = lambda f, c: img.getpixel(((c + 4) * modulo + modulo // 2, (f + 4) * modulo + modulo // 2))
    assert all((centro(f, c) == (0x2E, 0x2D, 0x2B)) == bool(matriz[f][c])
               for f in range(len(matriz)) for c in range(len(matriz)))


def test_refrescar_qr_escribe_svg_y_png_con_la_url_de_la_pieza(config_tmp):
    c, i = pieza_para_revisar(config_tmp, "Cuenco")
    url = refrescar_qr(c, i)
    assert url == url_pieza(URL_BASE, "cuenco")
    borrador = c.carpeta_borrador(i)
    assert (borrador / "qr.svg").is_file() and (borrador / "qr.png").is_file()
    c.editar_ficha(i, ficha("Jarra"))          # antes de aprobar el nombre manda: el QR se rehace
    assert refrescar_qr(c, i) == url_pieza(URL_BASE, "jarra")
    esperado = io.BytesIO()
    segno.make(url_pieza(URL_BASE, "jarra"), error="m").save(
        esperado, kind="svg", scale=8, border=4, dark="#2E2D2B", light="#F5F1E8")
    assert (borrador / "qr.svg").read_text() == esperado.getvalue().decode()


def test_completar_qr_cubre_las_piezas_existentes_y_salta_las_que_no_estan_listas(config_tmp):
    c, listas = pieza_para_revisar(config_tmp, "Cuenco")
    aprobada = c.crear_pieza()
    procesar_con_etapas_falsas(c, aprobada)
    c.guardar_ficha_borrador(aprobada, ficha("Bolso"))
    c.aprobar(aprobada)
    pendiente = c.crear_pieza()
    assert completar_qr(c) == 2
    for i in (listas, aprobada):
        assert (c.carpeta_borrador(i) / "qr.svg").is_file() and (c.carpeta_borrador(i) / "qr.png").is_file()
    assert c.obtener(pendiente).slug is None                    # no se le inventa dirección
    assert not (c.carpeta_borrador(pendiente) / "qr.svg").exists()


def test_etapa_qr_al_procesar(config_tmp):
    from panel.cola import Trabajador
    from panel.etapas import EtapaQR

    c = Cola(config_tmp)
    i = c.crear_pieza()

    class Ficha_:
        nombre = "ficha"

        def __call__(self, ctx):
            ctx.cola.guardar_ficha_borrador(ctx.pieza.id, Ficha("Cuenco", "Gres", "Cerámica", "Lavar a mano."))

    assert Trabajador(c, [EtapaFalsa(), Ficha_(), EtapaQR()]).procesar_uno()
    assert (c.carpeta_borrador(i) / "qr.svg").is_file() and (c.carpeta_borrador(i) / "qr.png").is_file()
    assert c.obtener(i).slug == "cuenco"


def test_api_sirve_qr_y_la_url(config_tmp):
    c, i = pieza_para_revisar(config_tmp, "Cuenco")
    cliente = TestClient(crear_app(config_tmp, etapas=[], iniciar_trabajador=False),
                         base_url="http://127.0.0.1")
    d = cliente.get(f"/api/piezas/{i}").json()           # crear_app completó el QR de lo que ya existía
    assert d["url_publica"] == url_pieza(URL_BASE, "cuenco") and d["slug_fijo"] is False
    assert "qr.svg" in d["archivos"] and "qr.png" in d["archivos"]
    r = cliente.get(f"/api/piezas/{i}/archivos/qr.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert cliente.get(f"/api/piezas/{i}/archivos/qr.svg").headers["content-type"] == "image/svg+xml"


def test_api_corregir_ficha_rehace_el_qr(config_tmp):
    c, i = pieza_para_revisar(config_tmp, "Cuenco")
    cliente = TestClient(crear_app(config_tmp, etapas=[], iniciar_trabajador=False),
                         base_url="http://127.0.0.1")
    r = cliente.put(f"/api/piezas/{i}/ficha", headers={"X-Vitrina": "panel"},
                    json={"nombre": "Jarra", "materiales": "Gres", "categoria": "Cerámica", "cuidados": "Lavar."})
    assert r.status_code == 200
    assert cliente.get(f"/api/piezas/{i}").json()["url_publica"] == url_pieza(URL_BASE, "jarra")
