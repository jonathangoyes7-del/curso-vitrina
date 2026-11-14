"""Lista de productos del panel (Tarea 16, solo la lista): foto, nombre y estado."""
import pytest

pytestmark = pytest.mark.navegador


def _tarjetas(panel_vivo, navegador):
    p = navegador.new_page()
    p.goto(panel_vivo)
    p.wait_for_selector(".pieza")
    return p


def test_una_tarjeta_por_producto(panel_vivo, navegador):
    p = _tarjetas(panel_vivo, navegador)
    assert p.locator(".pieza").count() == 2


def test_tarjeta_con_foto_nombre_y_estado(panel_vivo, navegador):
    p = _tarjetas(panel_vivo, navegador)
    t = p.locator(".pieza", has_text="Cuenco de gres")
    assert t.locator(".estado").inner_text() == "aprobada"
    foto = t.locator("img")
    foto.wait_for()
    # La foto se cargó de verdad (no es un icono roto).
    assert foto.evaluate("i => i.complete && i.naturalWidth > 0")
    assert "/archivos/portada.jpg" in foto.get_attribute("src")


def test_aprobada_se_distingue_del_borrador(panel_vivo, navegador):
    p = _tarjetas(panel_vivo, navegador)
    aprobada = p.locator(".pieza", has_text="Cuenco de gres")
    borrador = p.locator(".pieza", has_text="Jarra de barro")
    assert borrador.locator(".estado").inner_text() == "para revisar"
    assert "aprobada" in aprobada.get_attribute("class")
    assert "aprobada" not in borrador.get_attribute("class")
    color = lambda t: t.locator(".estado").evaluate("e => getComputedStyle(e).backgroundColor")
    assert color(aprobada) != color(borrador)
