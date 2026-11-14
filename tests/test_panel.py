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


# --- Revisión: abrir la ficha de un producto, corregirla, aprobarla o regenerarla ---

def _abrir(panel_vivo, navegador, nombre="Jarra de barro"):
    p = _tarjetas(panel_vivo, navegador)
    p.locator(".pieza", has_text=nombre).click()
    p.wait_for_selector("#revision form")
    return p


def test_pulsar_un_producto_abre_su_ficha(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    assert p.input_value("[name=nombre]") == "Jarra de barro"
    assert p.input_value("[name=materiales]") == "Gres"
    assert p.input_value("[name=cuidados]") == "Lavar a mano."
    assert p.input_value("[name=categoria]") == "Cerámica"


def test_categoria_es_select_de_tres(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    assert p.locator("select[name=categoria]").evaluate("s => s.tagName") == "SELECT"
    assert p.locator("select[name=categoria] option").all_inner_texts() == [
        "Cerámica", "Madera tallada", "Tejidos de lana"]


def test_guardar_corrige_la_ficha(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    p.fill("[name=nombre]", "Jarra azul")
    p.select_option("[name=categoria]", "Madera tallada")
    p.click("#revision >> text=Guardar")
    p.wait_for_selector("#revision >> text=Guardado")
    p.wait_for_selector(".pieza >> text=Jarra azul")
    # Persistió de verdad: al recargar y abrir de nuevo sigue ahí.
    p.reload()
    p.wait_for_selector(".pieza")
    p.locator(".pieza", has_text="Jarra azul").click()
    p.wait_for_selector("#revision form")
    assert p.input_value("[name=categoria]") == "Madera tallada"


def test_ficha_invalida_muestra_el_error_junto_al_campo(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    p.fill("[name=nombre]", "")
    p.click("#revision >> text=Guardar")
    p.wait_for_selector("[data-error=nombre]:not(:empty)")
    assert "obligatorio" in p.inner_text("[data-error=nombre]")


def test_aprobar_cambia_el_estado(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    p.once("dialog", lambda d: d.accept())
    p.click("#revision >> text=Aprobar")
    p.wait_for_selector(".pieza:has-text('Jarra de barro') .estado:text-is('aprobada')")


def test_aprobar_guarda_antes_los_cambios_sin_guardar(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    p.fill("[name=nombre]", "Jarra corregida")
    p.once("dialog", lambda d: d.accept())
    p.click("#revision >> text=Aprobar")
    p.wait_for_selector(".pieza:has-text('Jarra corregida') .estado:text-is('aprobada')")


def test_regenerar_ficha_vuelve_a_pendiente(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    p.once("dialog", lambda d: d.accept())
    p.click("#revision >> text=Volver a generar la ficha")
    p.wait_for_selector(".pieza:has-text('Jarra de barro') .estado:text-is('pendiente')")


def test_regenerar_pide_confirmacion_y_cancelar_no_hace_nada(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador)
    p.once("dialog", lambda d: d.dismiss())
    p.click("#revision >> text=Volver a generar la ficha")
    p.wait_for_timeout(500)
    assert p.locator(".pieza:has-text('Jarra de barro') .estado").inner_text() == "para revisar"


def test_pieza_aprobada_avisa_que_el_sitio_muestra_la_version_aprobada(panel_vivo, navegador):
    p = _abrir(panel_vivo, navegador, "Cuenco de gres")
    p.fill("[name=nombre]", "Cuenco nuevo")
    p.click("#revision >> text=Guardar")
    p.wait_for_selector("#revision >> text=El sitio sigue mostrando la versión aprobada hasta que apruebes esta.")
