"""Panel (Tarea 16, parte de subir fotos y cola): arrastrar, varias fotos, motivo del rechazo y avance."""
from pathlib import Path

import pytest
from PIL import Image, ImageFilter

pytestmark = pytest.mark.navegador

BUENA = Path(__file__).parent / "fixtures" / "fotos" / "ceramica.jpg"


@pytest.fixture
def borrosa(tmp_path):
    ruta = tmp_path / "borrosa.jpg"
    with Image.open(BUENA) as im:
        im.convert("RGB").filter(ImageFilter.GaussianBlur(8)).save(ruta, quality=90)
    return ruta


def _soltar(pagina, rutas):
    """Simula arrastrar archivos del escritorio y soltarlos sobre la página."""
    archivos = [{"nombre": Path(r).name, "datos": list(Path(r).read_bytes())} for r in rutas]
    pagina.evaluate(
        """(archivos) => {
            const dt = new DataTransfer();
            for (const a of archivos) dt.items.add(new File([new Uint8Array(a.datos)], a.nombre, {type: 'image/jpeg'}));
            const destino = document.querySelector('#zona');
            for (const tipo of ['dragenter', 'dragover', 'drop'])
                destino.dispatchEvent(new DragEvent(tipo, {dataTransfer: dt, bubbles: true, cancelable: true}));
        }""", archivos)


@pytest.fixture
def abrir(navegador):
    """Abre el panel en una página nueva y la cierra al acabar (si no, el SSE retrasa el apagado)."""
    paginas = []

    def _abrir(url):
        p = navegador.new_page()
        paginas.append(p)
        p.goto(url)
        p.wait_for_selector("#zona")
        return p

    yield _abrir
    for p in paginas:
        p.close()


def test_selector_acepta_varias_fotos(panel_con_cola, abrir):
    p = abrir(panel_con_cola[0])
    assert p.locator("input[type=file]").get_attribute("multiple") is not None


def test_subir_dos_fotos_con_el_selector(panel_con_cola, abrir):
    p = abrir(panel_con_cola[0])
    p.set_input_files("input[type=file]", [str(BUENA), str(BUENA)])
    p.click("text=Subir")
    p.wait_for_function("document.querySelectorAll('.pieza').length === 2")


def test_arrastrar_dos_fotos_las_sube(panel_con_cola, abrir):
    p = abrir(panel_con_cola[0])
    _soltar(p, [BUENA, BUENA])
    p.wait_for_function("document.querySelectorAll('.pieza').length === 2")


def test_la_zona_se_resalta_al_arrastrar(panel_con_cola, abrir):
    p = abrir(panel_con_cola[0])
    p.evaluate("""() => { const dt = new DataTransfer();
        document.querySelector('#zona').dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
    assert "arrastrando" in p.locator("#zona").get_attribute("class")


def test_foto_borrosa_muestra_el_motivo_y_no_entra(panel_con_cola, abrir, borrosa):
    p = abrir(panel_con_cola[0])
    _soltar(p, [borrosa])
    rechazo = p.locator("#resultados li", has_text="borrosa.jpg")
    rechazo.wait_for()
    assert "está borrosa" in rechazo.inner_text()
    assert p.locator(".pieza").count() == 0


def test_mezcla_sube_la_buena_y_explica_la_rechazada(panel_con_cola, abrir, borrosa):
    p = abrir(panel_con_cola[0])
    _soltar(p, [borrosa, BUENA])
    p.wait_for_function("document.querySelectorAll('.pieza').length === 1")
    assert "está borrosa" in p.locator("#resultados li", has_text="borrosa.jpg").inner_text()
    assert p.locator("#resultados li", has_text="ceramica.jpg").count() == 1


def test_una_tanda_nueva_reemplaza_los_resultados_de_la_anterior(panel_con_cola, abrir, borrosa):
    """Los resultados son de la última tanda: no se acumulan los de la anterior."""
    p = abrir(panel_con_cola[0])
    _soltar(p, [borrosa])
    p.wait_for_selector("#resultados li")
    _soltar(p, [BUENA])
    p.wait_for_function("document.querySelectorAll('.pieza').length === 1")
    assert p.locator("#resultados li", has_text="borrosa.jpg").count() == 0  # tanda nueva, resultados nuevos


def test_cola_muestra_barra_y_etapa_de_cada_trabajo(panel_con_cola, abrir):
    url, control = panel_con_cola
    p = abrir(url)
    _soltar(p, [BUENA, BUENA])
    assert control.en_curso.wait(timeout=15)
    primera, segunda = p.locator(".pieza").nth(1), p.locator(".pieza").nth(0)  # la lista pone la más nueva primero
    # El que se procesa: etapa en castellano, porcentaje y barra a medias.
    primera.locator(".etapa", has_text="Creando el modelo 3D").wait_for()
    assert "25 %" in primera.locator(".etapa").inner_text()
    assert primera.locator("progress").evaluate("b => b.value") == 25
    # El que espera su turno lo dice, con la barra vacía.
    assert "En espera" in segunda.locator(".etapa").inner_text()
    assert segunda.locator("progress").evaluate("b => b.value") == 0
    # Al dejar avanzar, la barra desaparece y ambos terminan para revisar.
    control.seguir.set()
    p.wait_for_function("[...document.querySelectorAll('.pieza .estado')].every(e => e.textContent === 'para revisar')", timeout=20_000)
    assert p.locator(".pieza progress").count() == 0
