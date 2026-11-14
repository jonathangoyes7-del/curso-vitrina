import json
import sqlite3
import threading
import time

import pytest
from fastapi.testclient import TestClient

from panel.api import crear_app
from panel.cola import Cola, Estado, Trabajador
from panel.progreso import Progreso, explicar_error, flujo_eventos
from tests.test_api import Etapa3DFalsa, H, subir


def test_progreso_por_etapa(config_tmp):
    vistos = []

    class Mira:
        def __init__(s, n): s.nombre = n

        def __call__(s, ctx):
            ctx.informar(0.5)
            vistos.append((s.nombre, ctx.cola.progreso(ctx.pieza.id).porcentaje))

    c = Cola(config_tmp); c.crear_pieza()
    Trabajador(c, [Mira("3d"), Mira("ficha")]).procesar_uno()
    assert vistos == [("3d", 25), ("ficha", 75)]


def test_informar_acota_la_fraccion(config_tmp):
    vistos = []

    class Mira:
        nombre = "3d"

        def __call__(s, ctx):
            ctx.informar(7); vistos.append(ctx.cola.progreso(ctx.pieza.id).fraccion)
            ctx.informar(-3); vistos.append(ctx.cola.progreso(ctx.pieza.id).fraccion)

    c = Cola(config_tmp); c.crear_pieza()
    Trabajador(c, [Mira()]).procesar_uno()
    assert vistos == [1.0, 0.0]


@pytest.mark.parametrize("estado,indice,total,fraccion,esperado", [
    (Estado.PENDIENTE, 0, 0, 0.0, 0),
    (Estado.PROCESANDO, 1, 4, 0.5, 38),
    (Estado.ERROR, 1, 4, 0.0, 25),
    (Estado.PARA_REVISAR, 0, 2, 0.0, 100),
    (Estado.PUBLICADA, 0, 0, 0.0, 100),
])
def test_porcentaje(estado, indice, total, fraccion, esperado):
    assert Progreso(estado, "3d", indice, total, fraccion).porcentaje == esperado


def test_pieza_terminada_marca_100(config_tmp):
    c = Cola(config_tmp); i = c.crear_pieza()

    class Ok:
        nombre = "3d"
        def __call__(s, ctx): pass

    Trabajador(c, [Ok()]).procesar_uno()
    assert c.progreso(i).porcentaje == 100


def test_reintentar_reinicia_el_progreso(config_tmp):
    c = Cola(config_tmp); i = c.crear_pieza()

    class Falla:
        nombre = "3d"
        def __call__(s, ctx): ctx.informar(0.9); raise RuntimeError("sin VRAM")

    Trabajador(c, [Falla()]).procesar_uno()
    assert c.obtener(i).error == "3d: sin VRAM" and c.progreso(i).etapa == "3d"
    c.aplicar(i, "reintentar")
    p = c.progreso(i)
    assert (p.estado, p.etapa, p.porcentaje) == (Estado.PENDIENTE, None, 0)


def test_migra_una_base_sin_columnas_de_progreso(config_tmp):
    config_tmp.datos.mkdir(parents=True)
    db = sqlite3.connect(config_tmp.datos / "vitrina.sqlite")
    db.execute("""CREATE TABLE piezas (id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT,
        slug_fijo INTEGER NOT NULL DEFAULT 0, estado TEXT NOT NULL, ficha_borrador TEXT,
        ficha_vigente TEXT, en_sitio INTEGER NOT NULL DEFAULT 0, es_ejemplo INTEGER NOT NULL DEFAULT 0,
        credito_autor TEXT, credito_url TEXT, error TEXT, creada TEXT NOT NULL, actualizada TEXT NOT NULL)""")
    db.execute("INSERT INTO piezas (estado, creada, actualizada) VALUES ('pendiente', 'x', 'x')")
    db.commit(); db.close()
    c = Cola(config_tmp)
    c.registrar_progreso(1, "3d", 0, 2, 0.5)
    assert c.progreso(1).porcentaje == 25
    Cola(config_tmp)  # migrar dos veces no falla


# --- errores legibles ---------------------------------------------------------------
def test_error_de_memoria_se_explica():
    e = explicar_error("3d: CUDA out of memory. Tried to allocate 2.00 GiB")
    assert "memoria" in e["titulo"].lower() and e["sugerencia"] and e["tecnico"].startswith("3d:")


def test_error_de_splat_demasiado_grande_se_explica():
    e = explicar_error("3d: el modelo supera el límite de 10.0 MB con todas las cantidades probadas: "
                       "262144 gaussianos = 11.0 MB")
    assert "pesa demasiado" in e["titulo"] and "11.0 MB" in e["tecnico"]


def test_error_desconocido_conserva_el_detalle():
    e = explicar_error("3d: algo raro")
    assert "modelo 3D" in e["titulo"] and "algo raro" in e["detalle"]


def test_sin_error_no_hay_explicacion():
    assert explicar_error(None) is None


# --- API y eventos --------------------------------------------------------------------
@pytest.fixture
def etapa():
    return Etapa3DFalsa()


@pytest.fixture
def app(config_tmp, etapa):
    return crear_app(config_tmp, etapas=[etapa], iniciar_trabajador=False)


@pytest.fixture
def cliente(app):
    return TestClient(app, base_url="http://127.0.0.1")


def test_endpoint_progreso(cliente):
    i = subir(cliente).json()["id"]
    r = cliente.get(f"/api/piezas/{i}/progreso")
    assert r.status_code == 200
    assert r.json() == {"estado": "pendiente", "etapa": None, "porcentaje": 0}
    assert cliente.get("/api/piezas/999/progreso").status_code == 404


def test_listado_incluye_progreso(cliente, app):
    i = subir(cliente).json()["id"]
    app.state.cola.registrar_progreso(i, "3d", 0, 2, 0.5)
    p = cliente.get("/api/piezas").json()[0]
    assert p["etapa"] == "3d" and p["porcentaje"] == 25


def test_error_en_el_listado_es_legible_y_se_puede_reintentar(config_tmp):
    etapa = Etapa3DFalsa(error="CUDA out of memory")
    app = crear_app(config_tmp, etapas=[etapa], iniciar_trabajador=False)
    cliente = TestClient(app, base_url="http://127.0.0.1")
    i = subir(cliente).json()["id"]
    app.state.trabajador.procesar_uno()
    p = cliente.get("/api/piezas").json()[0]
    assert p["estado"] == "error" and p["puede_reintentar"] is True
    assert "memoria" in p["error_legible"]["titulo"].lower()
    assert cliente.post(f"/api/piezas/{i}/reintentar").status_code == 403  # sin cabecera
    r = cliente.post(f"/api/piezas/{i}/reintentar", headers=H)
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"
    assert cliente.get(f"/api/piezas/{i}").json()["error"] is None
    assert cliente.post(f"/api/piezas/{i}/reintentar", headers=H).status_code == 409


def test_flujo_emite_al_cambiar_sin_sondeo(config_tmp):
    c = Cola(config_tmp); i = c.crear_pieza()
    parar = threading.Event()
    flujo = flujo_eventos(c, lambda: [{"porcentaje": c.progreso(i).porcentaje}], parar)
    assert "retry:" in next(flujo)
    primero = next(flujo)
    assert primero.startswith("event: piezas\n") and '"porcentaje": 0' in primero
    threading.Timer(0.2, lambda: c.registrar_progreso(i, "3d", 0, 2, 0.5)).start()
    t0 = time.monotonic()
    segundo = next(flujo)
    assert '"porcentaje": 25' in segundo and time.monotonic() - t0 < 1.5
    parar.set()
    assert list(flujo) == []


def test_flujo_manda_latido_si_no_pasa_nada(config_tmp):
    c = Cola(config_tmp)
    flujo = flujo_eventos(c, lambda: [], threading.Event(), latido=0.3, sondeo=0.1)
    next(flujo); next(flujo)
    assert next(flujo).startswith(":")


def test_endpoint_eventos_es_event_stream(cliente, app):
    subir(cliente)
    app.state.parar_eventos.set()  # el flujo entrega la foto actual y termina
    r = cliente.get("/api/eventos")
    assert r.headers["content-type"].startswith("text/event-stream")
    datos = [l for l in r.text.splitlines() if l.startswith("data: ")]
    assert json.loads(datos[0][6:])[0]["estado"] == "pendiente"
