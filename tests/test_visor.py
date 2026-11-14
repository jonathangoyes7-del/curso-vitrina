"""Tests del visor 3D (Three + Spark) en Chromium real."""
import pytest

from tests.utilidades import varianza_de_pixeles

pytestmark = pytest.mark.navegador


def _abrir(navegador, base, extra="", **ctx):
    p = navegador.new_context(viewport={"width": 800, "height": 600}, **ctx).new_page()
    p.goto(f"{base}/visor/ver.html?splat=/fixtures/mini.spz{extra}")
    p.wait_for_function("document.body.dataset.visor === 'listo'", timeout=30_000)
    return p


def test_mini_spz_es_valido():
    from pathlib import Path
    ruta = Path(__file__).parent / "fixtures" / "mini.spz"
    assert ruta.exists() and 0 < ruta.stat().st_size < 200_000


def test_carga_y_pinta(navegador, servidor_estatico):
    p = navegador.new_page(viewport={"width": 800, "height": 600})
    p.goto(f"{servidor_estatico}/visor/ver.html?splat=/fixtures/mini.spz")
    p.wait_for_function("document.body.dataset.visor === 'listo'", timeout=30_000)
    p.wait_for_timeout(500)
    assert varianza_de_pixeles(p.locator("canvas").screenshot()) > 10


def test_raton_gira(navegador, servidor_estatico):
    p = _abrir(navegador, servidor_estatico)
    antes = p.evaluate("window.visor.azimut()")
    p.mouse.move(400, 300)
    p.mouse.down()
    p.mouse.move(600, 300, steps=10)
    p.mouse.up()
    p.wait_for_timeout(300)
    despues = p.evaluate("window.visor.azimut()")
    assert abs(despues - antes) > 0.1


def test_dedo_gira(navegador, servidor_estatico):
    p = _abrir(navegador, servidor_estatico, has_touch=True)
    cdp = p.context.new_cdp_session(p)
    antes = p.evaluate("window.visor.azimut()")

    def toque(tipo, x):
        puntos = [] if tipo == "touchEnd" else [{"x": x, "y": 300, "id": 1}]
        cdp.send("Input.dispatchTouchEvent", {"type": tipo, "touchPoints": puntos})

    toque("touchStart", 300)
    for x in range(300, 521, 20):
        toque("touchMove", x)
    toque("touchEnd", 520)
    p.wait_for_timeout(300)
    despues = p.evaluate("window.visor.azimut()")
    assert abs(despues - antes) > 0.1


def test_splat_inexistente_muestra_error(navegador, servidor_estatico):
    p = navegador.new_page(viewport={"width": 800, "height": 600})
    p.goto(f"{servidor_estatico}/visor/ver.html?splat=/fixtures/no_existe.spz")
    p.wait_for_function("document.body.dataset.visor === 'error'", timeout=30_000)
    assert "No se pudo cargar la pieza en 3D." in p.inner_text("body")


def test_modo_reel_coloca_la_camara_por_cuadro(navegador, servidor_estatico):
    p = navegador.new_page(viewport={"width": 800, "height": 600})
    p.goto(f"{servidor_estatico}/visor/ver.html?splat=/fixtures/mini.spz&modo=reel")
    p.wait_for_function("document.body.dataset.visor === 'listo'", timeout=30_000)
    p.evaluate("window.visor.irACuadro(1, 4).then(() => 0)")
    az = p.evaluate("window.visor.azimut()")
    assert abs(az - 3.14159265 / 2) < 0.01


def test_gira_solo_y_se_para_al_tocar(navegador, servidor_estatico):
    p = _abrir(navegador, servidor_estatico)
    assert p.evaluate("window.visor.girando()")
    a0 = p.evaluate("window.visor.azimut()")
    p.wait_for_timeout(1500)
    a1 = p.evaluate("window.visor.azimut()")
    assert abs(a1 - a0) > 0.02          # se movió sin tocarlo
    assert abs(a1 - a0) < 0.5           # y despacio
    p.mouse.move(400, 300)
    p.mouse.down()
    p.mouse.up()
    assert not p.evaluate("window.visor.girando()")
    a2 = p.evaluate("window.visor.azimut()")
    p.wait_for_timeout(800)
    assert abs(p.evaluate("window.visor.azimut()") - a2) < 0.005


def test_no_se_acerca_ni_mira_desde_abajo(navegador, servidor_estatico):
    p = _abrir(navegador, servidor_estatico)
    p.mouse.move(400, 300)
    for _ in range(40):
        p.mouse.wheel(0, -400)          # acercar
    p.mouse.down()
    p.mouse.move(400, 100, steps=10)    # intentar mirar desde abajo
    p.mouse.up()
    p.wait_for_timeout(500)
    assert p.evaluate("window.visor.distancia()") >= 1.59
    assert p.evaluate("window.visor.altura()") >= -0.001


def test_boton_vuelve_a_la_vista_inicial(navegador, servidor_estatico):
    p = _abrir(navegador, servidor_estatico)
    inicial = p.evaluate("window.visor.distancia()")
    p.mouse.move(400, 300)
    p.mouse.wheel(0, -400)
    p.mouse.down()
    p.mouse.move(600, 250, steps=10)
    p.mouse.up()
    p.wait_for_timeout(300)
    assert abs(p.evaluate("window.visor.distancia()") - inicial) > 0.1
    p.get_by_role("button", name="Vista inicial").click()
    p.wait_for_timeout(800)
    assert abs(p.evaluate("window.visor.distancia()") - inicial) < 0.02
    assert abs(p.evaluate("window.visor.azimut()")) < 0.02
