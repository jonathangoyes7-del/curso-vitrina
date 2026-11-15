"""Generador del catálogo (Tarea 18): galería, estructura del sitio y verificación."""
import re
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from panel.catalogo.generador import (generar_sitio, publicas_desde_cola, renderizar_galeria,
                                      verificar_sitio)
from panel.catalogo.modelos import PiezaPublica
from panel.catalogo.rutas import rutas_absolutas_locales
from panel.cola import Cola
from panel.ficha import Ficha

URL = "https://jonathangoyes7-del.github.io/curso-vitrina/"
RAIZ = Path(__file__).resolve().parent.parent
LIMITE_SPZ, LIMITE_PAGINA = 10 * 1024 * 1024, 500 * 1024


def pieza_en_disco(tmp_path, slug, nombre="Cuenco", categoria="Cerámica", **extra):
    """Una pieza con su carpeta `vigente/` completa, con archivos que NO deben llegar al sitio."""
    carpeta = tmp_path / "vigente" / slug
    carpeta.mkdir(parents=True, exist_ok=True)
    shutil.copy(RAIZ / "tests" / "fixtures" / "mini.spz", carpeta / "pieza.spz")
    Image.new("RGB", (64, 64), (200, 120, 60)).save(carpeta / "portada.jpg")
    for sobrante in ("foto.jpg", "original.jpg", "entrada.png", "pieza.ply", "reel.mp4"):
        (carpeta / sobrante).write_bytes(b"no debe publicarse")
    datos = dict(es_ejemplo=False, credito_autor=None, credito_url=None)
    datos.update(extra)
    return PiezaPublica(slug=slug, ficha=Ficha(nombre, "Gres", categoria, "Lavar a mano."),
                        carpeta=carpeta, **datos)


def generado(tmp_path, *piezas):
    sitio = tmp_path / "sitio"
    generar_sitio(list(piezas) or [pieza_en_disco(tmp_path, "cuenco")], sitio, RAIZ, URL)
    return sitio


def test_genera_estructura(tmp_path):
    sitio = tmp_path / "sitio"
    generar_sitio([pieza_en_disco(tmp_path, "cuenco")], sitio, RAIZ, URL)
    for r in ["index.html", ".nojekyll", ".vitrina-sitio", "estilos.css", "compartir.js", "galeria.js",
              "visor/visor.js", "piezas/cuenco/index.html", "piezas/cuenco/pieza.spz",
              "piezas/cuenco/portada.jpg", "piezas/cuenco/qr.svg", "embed/cuenco/index.html",
              "componente/vitrina-pieza.js", "vendor/three/three.module.js", "vendor/three/three.core.js",
              "vendor/three/addons/controls/OrbitControls.js", "vendor/three/addons/postprocessing/Pass.js",
              "vendor/three/LICENSE", "vendor/spark/spark.module.js", "vendor/spark/LICENSE"]:
        assert (sitio / r).exists(), r
    for prohibido in ("*.ply", "*.mp4", "foto.jpg", "original.*", "entrada.png"):
        assert not list(sitio.rglob(prohibido)), prohibido


def test_galeria_no_carga_visor(tmp_path):
    html = (generado(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "spark" not in html.lower() and "three" not in html.lower() and "visor" not in html


def test_galeria_una_tarjeta_por_pieza():
    p1 = PiezaPublica("cuenco", Ficha("Cuenco", "Gres", "Cerámica", "x"), False, None, None, Path("v"))
    p2 = PiezaPublica("cesto", Ficha("Cesto <b>", "Lana", "Tejidos de lana", "x"), True, "Ana Pérez",
                      "https://unsplash.com/@ana", Path("v"))
    html = renderizar_galeria([p1, p2])
    assert html.count('class="tarjeta"') == 2
    assert 'href="piezas/cuenco/"' in html and 'src="piezas/cuenco/portada.jpg"' in html
    assert 'loading="lazy"' in html and 'alt="Cuenco"' in html and 'data-categoria="Cerámica"' in html
    assert "Cesto &lt;b&gt;" in html and html.count(">Ejemplo<") == 1
    assert "Foto de «Cesto &lt;b&gt;»" in html and "Ana Pérez" in html and "Built with DINOv3" in html
    assert not rutas_absolutas_locales(html)


def test_todas_las_paginas_enlazan_a_creditos(tmp_path):
    sitio = generado(tmp_path)
    leer = lambda r: (sitio / r).read_text(encoding="utf-8")
    assert 'href="creditos/"' in leer("index.html")
    assert 'href="../../creditos/"' in leer("piezas/cuenco/index.html")
    assert 'href="../../creditos/"' in leer("embed/cuenco/index.html")
    assert 'href="../"' in leer("creditos/index.html")
    assert verificar_sitio(sitio, LIMITE_SPZ, LIMITE_PAGINA) == []


def test_galeria_vacia_enlaza_a_creditos():
    assert 'href="creditos/"' in renderizar_galeria([])


def test_galeria_vacia():
    html = renderizar_galeria([])
    assert "Todavía no hay piezas publicadas." in html and 'class="tarjeta"' not in html
    assert "Built with DINOv3" in html


def test_sitio_sin_piezas_se_genera_y_lo_dice(tmp_path):
    sitio = tmp_path / "sitio"
    generar_sitio([], sitio, RAIZ, URL)
    assert "Todavía no hay piezas publicadas." in (sitio / "index.html").read_text(encoding="utf-8")
    assert verificar_sitio(sitio, LIMITE_SPZ, LIMITE_PAGINA) == []


def test_filtro_tiene_tres_categorias():
    html = renderizar_galeria([PiezaPublica("a", Ficha("A", "x", "Cerámica", "x"), False, None, None, Path("v"))])
    for etiqueta in ("Todas", "Cerámica", "Madera tallada", "Tejidos de lana"):
        assert f">{etiqueta}</button>" in html
    assert html.count("<button") == 4


def test_galeria_tiene_buscador_y_aviso_oculto():
    html = renderizar_galeria([PiezaPublica("a", Ficha("Cuenco", "x", "Cerámica", "x"), False, None, None, Path("v"))])
    assert 'type="search"' in html and 'for="buscar"' in html and 'data-nombre="Cuenco"' in html
    assert re.search(r'class="sin-resultados"[^>]*\bhidden\b', html) and 'class="buscador" hidden' in html
    assert html.count("<button") == 4          # el buscador no añade botones al filtro


def test_galeria_vacia_sin_buscador():
    html = renderizar_galeria([])
    assert "<input" not in html and 'class="sin-resultados"' not in html and 'class="buscador"' not in html


def test_verificar_sitio_limpio(tmp_path):
    assert verificar_sitio(generado(tmp_path), LIMITE_SPZ, LIMITE_PAGINA) == []


def test_verificar_detecta_exif(tmp_path):
    sitio = generado(tmp_path)
    im = Image.new("RGB", (32, 32))
    exif = Image.Exif()
    exif[0x8825] = {1: "N"}   # bloque GPS
    exif[0x010F] = "Cámara"
    im.save(sitio / "piezas" / "cuenco" / "portada.jpg", exif=exif)
    problemas = verificar_sitio(sitio, LIMITE_SPZ, LIMITE_PAGINA)
    assert any("EXIF" in p and "portada.jpg" in p for p in problemas)


def test_verificar_detecta_spz_grande(tmp_path):
    sitio = generado(tmp_path)
    assert any("pieza.spz" in p and "límite" in p for p in verificar_sitio(sitio, 1000, LIMITE_PAGINA))


def test_verificar_detecta_archivo_no_permitido_y_ruta_absoluta(tmp_path):
    sitio = generado(tmp_path)
    (sitio / "pieza.ply").write_bytes(b"x")
    (sitio / "malo.html").write_text('<a href="/x">x</a>', encoding="utf-8")
    problemas = " ".join(verificar_sitio(sitio, LIMITE_SPZ, LIMITE_PAGINA))
    assert "pieza.ply" in problemas and "«/x»" in problemas


def test_verificar_detecta_pagina_pesada(tmp_path):
    sitio = generado(tmp_path)
    assert any("pesa" in p and "gzip" in p for p in verificar_sitio(sitio, LIMITE_SPZ, 1024))


def test_no_borra_carpeta_ajena(tmp_path):
    with pytest.raises(ValueError):
        generar_sitio([], tmp_path / "docs", RAIZ, URL)
    ajena = tmp_path / "sitio"
    ajena.mkdir()
    (ajena / "mis_cosas.txt").write_text("importante", encoding="utf-8")
    with pytest.raises(ValueError):
        generar_sitio([], ajena, RAIZ, URL)
    assert (ajena / "mis_cosas.txt").read_text(encoding="utf-8") == "importante"


def test_regenerar_vacia_lo_anterior(tmp_path):
    sitio = generado(tmp_path, pieza_en_disco(tmp_path, "cuenco"), pieza_en_disco(tmp_path, "jarra"))
    assert (sitio / "piezas" / "jarra").is_dir()
    generar_sitio([pieza_en_disco(tmp_path, "cuenco")], sitio, RAIZ, URL)
    assert not (sitio / "piezas" / "jarra").exists() and not (sitio / "embed" / "jarra").exists()
    assert not [d for d in tmp_path.iterdir() if d.name.startswith("sitio-")]   # sin temporales


def test_falla_si_falta_portada_y_no_toca_el_sitio_anterior(tmp_path):
    sitio = generado(tmp_path)
    mala = pieza_en_disco(tmp_path, "jarra")
    (mala.carpeta / "portada.jpg").unlink()
    with pytest.raises(ValueError, match="portada.jpg"):
        generar_sitio([mala], sitio, RAIZ, URL)
    assert (sitio / "piezas" / "cuenco" / "index.html").exists()


def test_rechaza_slug_raro(tmp_path):
    with pytest.raises(ValueError):
        generar_sitio([pieza_en_disco(tmp_path, "../fuera")], tmp_path / "sitio", RAIZ, URL)


# --- Desde la cola: solo lo aprobado, y con la versión aprobada ------------------------------

def test_publicas_solo_aprobadas_y_con_la_ficha_vigente(config_tmp):
    cola = Cola(config_tmp)
    ids = {}
    for nombre in ("Cuenco", "Jarra", "Cesto"):
        i = cola.crear_pieza()
        b = cola.carpeta_borrador(i)
        b.mkdir(parents=True)
        shutil.copy(RAIZ / "tests" / "fixtures" / "mini.spz", b / "pieza.spz")
        Image.new("RGB", (8, 8)).save(b / "portada.jpg")
        cola.guardar_ficha_borrador(i, Ficha(nombre, "Gres", "Cerámica", "x"))
        cola.fijar_slug(i, nombre.lower())
        cola.aplicar(i, "empezar"); cola.aplicar(i, "terminar")
        ids[nombre] = i
    cola.aprobar(ids["Cuenco"])
    cola.aprobar(ids["Jarra"]); cola.despublicar(ids["Jarra"])
    cola.editar_ficha(ids["Cuenco"], Ficha("Cuenco editado", "Gres", "Cerámica", "x"))   # borrador nuevo
    publicas = publicas_desde_cola(cola)
    assert [p.slug for p in publicas] == ["cuenco"]          # ni la despublicada ni la que sigue en revisión
    assert publicas[0].ficha.nombre == "Cuenco"              # la aprobada, no el borrador
    assert publicas[0].carpeta == cola.carpeta_vigente(ids["Cuenco"])
    cola.cerrar()


@pytest.mark.navegador
def test_busqueda_en_navegador(navegador, tmp_path):
    from tests.conftest import servir_carpetas
    sitio = generado(tmp_path,
                     pieza_en_disco(tmp_path, "cantaro", "Cántaro", "Cerámica"),
                     pieza_en_disco(tmp_path, "cesto", "Cesto", "Tejidos de lana"),
                     pieza_en_disco(tmp_path, "tallado", "Tallado", "Madera tallada"))
    srv, url = servir_carpetas({"/curso-vitrina": sitio})
    try:
        p = navegador.new_page(viewport={"width": 1000, "height": 900})
        errores = []
        p.on("pageerror", lambda e: errores.append(str(e)))
        p.goto(f"{url}/curso-vitrina/")
        caja = p.get_by_label("Buscar por nombre o categoría")
        aviso = p.locator(".sin-resultados")
        visibles = p.locator(".tarjeta:visible")
        assert visibles.count() == 3 and not aviso.is_visible()

        for consulta in ("CANTARO", "cántaro", "cantaro"):          # sin importar tildes ni mayúsculas
            caja.fill(consulta)
            assert visibles.count() == 1 and visibles.locator("h2").inner_text() == "Cántaro"
        caja.fill("CERAMICA")                                        # por categoría
        assert visibles.count() == 1 and visibles.locator("h2").inner_text() == "Cántaro"
        caja.fill("tejidos")
        assert visibles.locator("h2").inner_text() == "Cesto"

        caja.fill("zzz")                                             # nada: avisa
        assert visibles.count() == 0 and aviso.is_visible()
        assert "No hay piezas" in aviso.inner_text()

        caja.fill("")                                                # borrar: vuelven todas, sin aviso
        assert visibles.count() == 3 and not aviso.is_visible()

        p.get_by_role("button", name="Madera tallada").click()       # búsqueda y filtro a la vez
        caja.fill("ta")
        assert visibles.count() == 1 and visibles.locator("h2").inner_text() == "Tallado"
        caja.fill("cesto")
        assert visibles.count() == 0 and aviso.is_visible()
        assert not errores
    finally:
        srv.shutdown()


@pytest.mark.navegador
def test_sitio_navegable(navegador, tmp_path):
    from tests.conftest import servir_carpetas
    sitio = generado(tmp_path,
                     pieza_en_disco(tmp_path, "cuenco", "Cuenco", "Cerámica"),
                     pieza_en_disco(tmp_path, "cesto", "Cesto", "Tejidos de lana"))
    # Como GitHub Pages: el sitio cuelga de la subruta /curso-vitrina/
    srv, url = servir_carpetas({"/curso-vitrina": sitio})
    try:
        p = navegador.new_page(viewport={"width": 1000, "height": 900})
        errores = []
        p.on("pageerror", lambda e: errores.append(str(e)))
        p.goto(f"{url}/curso-vitrina/")
        assert p.locator(".tarjeta:visible").count() == 2
        p.get_by_role("button", name="Tejidos de lana").click()
        assert p.locator(".tarjeta:visible").count() == 1
        assert p.locator(".tarjeta:visible h2").inner_text() == "Cesto"
        p.get_by_role("button", name="Todas").click()
        assert p.locator(".tarjeta:visible").count() == 2
        p.locator(".tarjeta", has_text="Cuenco").click()
        p.wait_for_url("**/curso-vitrina/piezas/cuenco/")
        p.wait_for_function("document.body.dataset.visor === 'listo'", timeout=30_000)
        p.get_by_role("link", name="← Volver al catálogo").click()
        p.wait_for_url(f"{url}/curso-vitrina/")
        assert not errores
    finally:
        srv.shutdown()
