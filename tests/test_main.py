"""Lanzador (Tarea 21): solo localhost, comprobación del entorno al arrancar y botón de publicar."""
import inspect
from dataclasses import replace

import httpx
import pytest

import panel.__main__ as lanzador
from panel.__main__ import main
from panel.entorno import comprobar_entorno, comprobar_gpu, comprobar_ollama


@pytest.fixture
def lanzado(monkeypatch, config_tmp):
    """Ejecuta `main()` sin servidor ni navegador reales; devuelve lo que habría recibido uvicorn."""
    llamadas = {"navegador": []}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: llamadas.update(kw, app=app))
    monkeypatch.setattr("webbrowser.open", lambda url, *a, **k: llamadas["navegador"].append(url))
    monkeypatch.setattr(lanzador, "etapas_reales", lambda c: [])
    monkeypatch.setattr(lanzador.Config, "por_defecto", classmethod(lambda cls: config_tmp))
    monkeypatch.setattr(lanzador, "puerto_ocupado", lambda host, puerto: False)
    monkeypatch.setattr(lanzador, "comprobar_entorno",
                        lambda c: {"ollama": {"listo": True, "mensaje": "Ollama listo"},
                                   "gpu": {"listo": True, "mensaje": "GPU lista"}})
    return llamadas


def test_escucha_solo_en_localhost(lanzado):
    main()
    assert lanzado["host"] == "127.0.0.1" and lanzado["port"] == 8765


def test_main_sin_parametros():
    assert not inspect.signature(main).parameters


def test_abre_el_navegador_en_el_panel(lanzado):
    main()
    lanzado["app"].router.lifespan_context  # la app existe
    import time
    for _ in range(50):  # el aviso al navegador va en un temporizador corto
        if lanzado["navegador"]:
            break
        time.sleep(0.1)
    assert lanzado["navegador"] == ["http://127.0.0.1:8765/"]


def test_si_el_panel_ya_esta_abierto_no_arranca_otro(lanzado, monkeypatch):
    monkeypatch.setattr(lanzador, "puerto_ocupado", lambda host, puerto: True)
    main()
    assert "port" not in lanzado  # uvicorn no se llamó
    assert lanzado["navegador"] == ["http://127.0.0.1:8765/"]  # solo se abre el que ya había


def test_al_arrancar_dice_si_ollama_y_la_gpu_estan_listos(lanzado, capsys, monkeypatch):
    monkeypatch.setattr(lanzador, "comprobar_entorno",
                        lambda c: {"ollama": {"listo": False, "mensaje": "Ollama está apagado"},
                                   "gpu": {"listo": True, "mensaje": "GPU lista: RTX"}})
    main()
    salida = capsys.readouterr().out
    assert "Ollama está apagado" in salida and "GPU lista: RTX" in salida
    assert "port" in lanzado  # aun con Ollama apagado el panel abre: avisa, no se niega


# --- Comprobaciones del entorno ---

def _ollama_falso(monkeypatch, respuesta=None, error=None):
    def get(url, **kw):
        if error:
            raise error
        return respuesta
    monkeypatch.setattr(httpx, "get", get)


def _resp(modelos):
    return httpx.Response(200, json={"models": [{"name": m} for m in modelos]},
                          request=httpx.Request("GET", "http://x"))


def test_ollama_apagado_se_explica_con_claridad(monkeypatch, config_tmp):
    _ollama_falso(monkeypatch, error=httpx.ConnectError("sin conexión"))
    r = comprobar_ollama(config_tmp)
    assert r["listo"] is False
    assert "apagado" in r["mensaje"] and "Ollama" in r["mensaje"]


def test_ollama_sin_el_modelo_dice_que_descargarlo(monkeypatch, config_tmp):
    _ollama_falso(monkeypatch, respuesta=_resp(["otro:7b"]))
    r = comprobar_ollama(config_tmp)
    assert r["listo"] is False and f"ollama pull {config_tmp.modelo_ficha}" in r["mensaje"]


def test_ollama_con_el_modelo_esta_listo(monkeypatch, config_tmp):
    _ollama_falso(monkeypatch, respuesta=_resp([config_tmp.modelo_ficha]))
    assert comprobar_ollama(config_tmp)["listo"] is True


def test_gpu_sin_cuda_avisa(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    r = comprobar_gpu()
    assert r["listo"] is False and "tarjeta gráfica" in r["mensaje"]


def test_comprobar_entorno_junta_las_dos(monkeypatch, config_tmp):
    monkeypatch.setattr("panel.entorno.comprobar_ollama", lambda c: {"listo": True, "mensaje": "o"})
    monkeypatch.setattr("panel.entorno.comprobar_gpu", lambda: {"listo": False, "mensaje": "g"})
    assert comprobar_entorno(config_tmp) == {"ollama": {"listo": True, "mensaje": "o"},
                                             "gpu": {"listo": False, "mensaje": "g"}}


# --- API: estado del entorno y publicar ---

@pytest.fixture
def cliente(config_tmp):
    from fastapi.testclient import TestClient

    from panel.api import crear_app
    publicaciones = []

    def publicar_falso():
        publicaciones.append(1)
        return {"sha": "abc123", "piezas": 2, "url": config_tmp.url_publica}

    app = crear_app(config_tmp, etapas=[], iniciar_trabajador=False, publicar=publicar_falso,
                    entorno=lambda: {"ollama": {"listo": False, "mensaje": "Ollama está apagado"},
                                     "gpu": {"listo": True, "mensaje": "GPU lista"}})
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        c.publicaciones = publicaciones
        yield c


H = {"X-Vitrina": "panel"}


def test_api_estado_devuelve_el_entorno(cliente):
    d = cliente.get("/api/estado").json()
    assert d["ollama"]["listo"] is False and d["gpu"]["listo"] is True


def test_api_publicar_ejecuta_la_publicacion(cliente):
    r = cliente.post("/api/publicar", headers=H)
    assert r.status_code == 200 and r.json()["sha"] == "abc123"
    assert cliente.publicaciones == [1]


def test_api_publicar_exige_la_cabecera(cliente):
    assert cliente.post("/api/publicar").status_code == 403
    assert cliente.publicaciones == []


def test_api_publicar_informa_del_error(config_tmp):
    from fastapi.testclient import TestClient

    from panel.api import crear_app
    from panel.catalogo.publicar import ErrorPublicacion

    def falla():
        raise ErrorPublicacion("git push falló: sin red")

    app = crear_app(config_tmp, etapas=[], iniciar_trabajador=False, publicar=falla)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        r = c.post("/api/publicar", headers=H)
    assert r.status_code == 502 and "sin red" in r.json()["detail"]


def test_api_publicar_no_corre_dos_veces_a_la_vez(config_tmp):
    import threading

    from fastapi.testclient import TestClient

    from panel.api import crear_app
    dentro, soltar = threading.Event(), threading.Event()

    def lenta():
        dentro.set()
        soltar.wait(5)
        return {"sha": "x", "piezas": 0, "url": ""}

    app = crear_app(config_tmp, etapas=[], iniciar_trabajador=False, publicar=lenta)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        primero = threading.Thread(target=lambda: c.post("/api/publicar", headers=H))
        primero.start()
        assert dentro.wait(5)
        assert c.post("/api/publicar", headers=H).status_code == 409
        soltar.set()
        primero.join(5)


def test_api_publicacion_cuenta_las_piezas_del_sitio(cliente):
    d = cliente.get("/api/publicacion").json()
    assert d["piezas"] == 0 and d["url"].startswith("https://")


# --- En el navegador: aviso de Ollama y confirmación antes de publicar ---

@pytest.fixture
def panel_publicable(config_tmp):
    """Panel con Ollama «apagado» (que luego se enciende) y una publicación falsa que cuenta sus llamadas."""
    from panel.api import crear_app
    from tests.conftest import _servir
    estado = {"ollama": False, "publicaciones": 0, "fallar": False}

    def entorno():
        ollama = ({"listo": True, "mensaje": "Ollama listo"} if estado["ollama"]
                  else {"listo": False, "mensaje": "Ollama está apagado o no responde. Ábrelo."})
        return {"ollama": ollama, "gpu": {"listo": True, "mensaje": "GPU lista"}}

    def publicar():
        estado["publicaciones"] += 1
        if estado["fallar"]:
            from panel.catalogo.publicar import ErrorPublicacion
            raise ErrorPublicacion("git push falló: sin red")
        return {"sha": "abc", "piezas": 0, "url": config_tmp.url_publica}

    servidor, hilo, url = _servir(crear_app(config_tmp, etapas=[], iniciar_trabajador=False,
                                            publicar=publicar, entorno=entorno))
    yield url, estado
    servidor.should_exit = True
    hilo.join(timeout=5)


@pytest.mark.navegador
def test_ollama_apagado_se_avisa_y_al_encenderlo_se_quita(panel_publicable, navegador):
    url, estado = panel_publicable
    p = navegador.new_page()
    p.goto(url)
    p.wait_for_selector("#entorno-avisos li")
    assert "Ollama está apagado" in p.inner_text("#entorno-avisos")
    estado["ollama"] = True
    p.click("#recomprobar")
    p.wait_for_selector("#entorno-avisos li", state="detached")
    assert "listos" in p.inner_text("#entorno-resumen")
    assert not p.locator("#recomprobar").is_visible()


@pytest.mark.navegador
def test_publicar_pide_confirmacion_en_la_pagina_y_cancelar_no_publica(panel_publicable, navegador):
    url, estado = panel_publicable
    p = navegador.new_page()
    dialogos = []
    p.on("dialog", lambda d: (dialogos.append(d), d.dismiss()))
    p.goto(url)
    p.click("#publicar-abrir")
    p.wait_for_selector("#publicar-confirmar:not([hidden])")
    assert "Vas a publicar" in p.inner_text("#publicar-texto") or "No hay ninguna pieza" in p.inner_text("#publicar-texto")
    assert estado["publicaciones"] == 0       # preguntar no publica
    p.click("#publicar-no")
    p.wait_for_selector("#publicar-confirmar", state="hidden")
    assert estado["publicaciones"] == 0 and "No se publicó nada" in p.inner_text("#publicar-resultado")
    assert dialogos == []                      # la confirmación es de la página, no un cuadro del navegador


@pytest.mark.navegador
def test_publicar_tras_confirmar(panel_publicable, navegador):
    url, estado = panel_publicable
    p = navegador.new_page()
    p.goto(url)
    p.click("#publicar-abrir")
    p.click("#publicar-si")
    p.wait_for_selector("#publicar-resultado.bien")
    assert estado["publicaciones"] == 1 and "Publicado" in p.inner_text("#publicar-resultado")
    assert p.locator("#publicar-abrir").is_enabled()


@pytest.mark.navegador
def test_publicar_con_error_lo_cuenta(panel_publicable, navegador):
    url, estado = panel_publicable
    estado["fallar"] = True
    p = navegador.new_page()
    p.goto(url)
    p.click("#publicar-abrir")
    p.click("#publicar-si")
    p.wait_for_selector("#publicar-resultado.mal")
    assert "sin red" in p.inner_text("#publicar-resultado") and "No se publicó" in p.inner_text("#publicar-resultado")
