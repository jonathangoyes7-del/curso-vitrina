import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter

from panel.api import crear_app
from panel.cola import Estado

H = {"X-Vitrina": "panel"}
FIXTURE = Path(__file__).parent / "fixtures" / "fotos" / "ceramica.jpg"


class Etapa3DFalsa:
    nombre = "3d"

    def __init__(self, error=None):
        self.error, self.vistas = error, []

    def __call__(self, ctx):
        self.vistas.append((ctx.pieza.id, (ctx.borrador / "foto.jpg").is_file()))
        if self.error:
            raise RuntimeError(self.error)
        (ctx.borrador / "pieza.ply").write_bytes(b"ply")
        (ctx.borrador / "entrada.png").write_bytes(b"png")


@pytest.fixture
def etapa():
    return Etapa3DFalsa()


@pytest.fixture
def app(config_tmp, etapa):
    return crear_app(config_tmp, etapas=[etapa], iniciar_trabajador=False)


@pytest.fixture
def cliente(app):
    return TestClient(app, base_url="http://127.0.0.1")


def subir(cliente, ruta=FIXTURE, **extra):
    with open(ruta, "rb") as f:
        return cliente.post("/api/piezas", files={"foto": (Path(ruta).name, f, "image/jpeg")},
                            data=extra, headers=H)


def test_subir_foto_valida(cliente, config_tmp):
    r = subir(cliente)
    assert r.status_code == 201 and r.json()["estado"] == "pendiente"
    carpeta = config_tmp.carpeta_piezas / str(r.json()["id"])
    assert (carpeta / "borrador" / "foto.jpg").exists()
    assert (carpeta / "borrador" / "portada.jpg").exists()
    assert (carpeta / "original.jpg").exists()


def test_subir_foto_borrosa_422(cliente, config_tmp, tmp_path):
    with Image.open(FIXTURE) as im:
        im.filter(ImageFilter.GaussianBlur(6)).save(tmp_path / "borrosa.jpg")
    r = subir(cliente, tmp_path / "borrosa.jpg")
    assert r.status_code == 422 and r.json()["problemas"]
    assert cliente.get("/api/piezas").json() == []
    assert not list(config_tmp.carpeta_piezas.glob("*"))


def test_subir_no_imagen_422(cliente, tmp_path):
    (tmp_path / "x.jpg").write_text("no soy una foto")
    assert subir(cliente, tmp_path / "x.jpg").status_code == 422


def test_listar_y_detalle(cliente):
    i = subir(cliente, credito_autor="Ana", es_ejemplo="true").json()["id"]
    lista = cliente.get("/api/piezas").json()
    assert lista == [{"id": i, "slug": None, "estado": "pendiente", "nombre": None,
                      "error": None, "es_ejemplo": True, "etapa": None, "etapa_texto": None,
                      "porcentaje": 0, "error_legible": None, "puede_reintentar": False}]
    det = cliente.get(f"/api/piezas/{i}").json()
    assert det["archivos"]["foto.jpg"] == f"/api/piezas/{i}/archivos/foto.jpg"
    assert "pieza.spz" not in det["archivos"]
    assert cliente.get(f"/api/piezas/{'0' * 32}").status_code == 404
    assert cliente.get("/api/piezas/999").status_code == 404
    assert cliente.get("/api/piezas/abc").status_code == 404
    assert cliente.get(f"/api/piezas/{9 * 10**30}").status_code == 404


def test_servir_archivo_permitido(cliente):
    i = subir(cliente).json()["id"]
    r = cliente.get(f"/api/piezas/{i}/archivos/portada.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_archivo_no_permitido_404(cliente):
    i = subir(cliente).json()["id"]
    assert cliente.get(f"/api/piezas/{i}/archivos/original.jpg").status_code == 404
    assert cliente.get(f"/api/piezas/{i}/archivos/..%2Fvitrina.sqlite").status_code == 404
    assert cliente.get("/api/piezas/..%2F..%2Fx/archivos/foto.jpg").status_code == 404


def test_post_sin_cabecera_rechazado(cliente):
    with open(FIXTURE, "rb") as f:
        r = cliente.post("/api/piezas", files={"foto": ("c.jpg", f, "image/jpeg")})
    assert r.status_code == 403
    assert cliente.get("/api/piezas").json() == []


def test_host_ajeno_rechazado(app):
    assert TestClient(app, base_url="http://vitrina.evil.example").get("/api/piezas").status_code == 400


def test_docs_permite_probar_subida(cliente):
    esquema = cliente.get("/openapi.json").json()
    post = esquema["paths"]["/api/piezas"]["post"]
    assert cliente.get("/docs").status_code == 200
    assert any(p["name"] == "X-Vitrina" and p["schema"].get("default") == "panel"
               for p in post["parameters"])
    assert "multipart/form-data" in post["requestBody"]["content"]


def test_raiz_sirve_panel(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "Vitrina" in r.text


def test_subida_entra_en_la_cola(cliente, app):
    i = subir(cliente, credito_autor="Ana", credito_url="https://unsplash.com/@ana").json()["id"]
    p = app.state.cola.obtener(i)
    assert p.estado is Estado.PENDIENTE and p.credito_autor == "Ana"
    assert p.credito_url == "https://unsplash.com/@ana"


def test_subida_rechazada_no_entra_en_la_cola(cliente, app, tmp_path):
    (tmp_path / "x.jpg").write_text("no soy una foto")
    subir(cliente, tmp_path / "x.jpg")
    assert app.state.cola.listar() == []


def test_trabajador_convierte_la_subida(cliente, app, etapa):
    i = subir(cliente).json()["id"]
    assert app.state.trabajador.procesar_uno() is True
    assert etapa.vistas == [(i, True)]  # la foto limpia ya estaba en borrador/
    det = cliente.get(f"/api/piezas/{i}").json()
    assert det["estado"] == "para revisar" and det["error"] is None
    assert det["archivos"]["entrada.png"] == f"/api/piezas/{i}/archivos/entrada.png"
    assert cliente.get("/api/piezas").json()[0]["estado"] == "para revisar"


def test_error_del_trabajo_visible(config_tmp):
    app = crear_app(config_tmp, etapas=[Etapa3DFalsa(error="sin VRAM")], iniciar_trabajador=False)
    cli = TestClient(app, base_url="http://127.0.0.1")
    i = subir(cli).json()["id"]
    app.state.trabajador.procesar_uno()
    det = cli.get(f"/api/piezas/{i}").json()
    assert det["estado"] == "error" and det["error"] == "3d: sin VRAM"


def test_listar_mas_nuevas_primero(cliente):
    a = subir(cliente).json()["id"]
    b = subir(cliente).json()["id"]
    assert [p["id"] for p in cliente.get("/api/piezas").json()] == [b, a]


def test_trabajador_arranca_con_el_servidor(config_tmp):
    app = crear_app(config_tmp, etapas=[Etapa3DFalsa()])
    with TestClient(app, base_url="http://127.0.0.1") as cli:
        i = subir(cli).json()["id"]
        limite = time.monotonic() + 10
        while cli.get(f"/api/piezas/{i}").json()["estado"] != "para revisar":
            assert time.monotonic() < limite, "el trabajador no procesó la pieza"
            time.sleep(0.1)
    assert app.state.trabajador._hilo is None  # se detuvo al cerrar


def test_etapas_por_defecto_son_las_reales(config_tmp):
    app = crear_app(config_tmp, iniciar_trabajador=False)
    assert [e.nombre for e in app.state.trabajador.etapas] == ["3d"]


def test_subida_con_carpeta_huerfana(cliente, app, config_tmp):
    # datos/vitrina.sqlite reseteada pero quedan carpetas: la subida no se bloquea.
    huerfana = config_tmp.carpeta_piezas / "1"
    huerfana.mkdir(parents=True)
    (huerfana / "original.jpg").write_bytes(b"antigua")
    r = subir(cliente)
    assert r.status_code == 201
    assert (config_tmp.carpeta_piezas / str(r.json()["id"]) / "borrador" / "foto.jpg").is_file()
    apartadas = list(config_tmp.carpeta_piezas.glob(".huerfana-1-*"))
    assert len(apartadas) == 1 and (apartadas[0] / "original.jpg").read_bytes() == b"antigua"


def test_fallo_al_confirmar_no_deja_carpeta(cliente, app, config_tmp, monkeypatch):
    original = app.state.cola.crear_pieza

    def crear_y_fallar(**kw):
        preparar = kw.pop("preparar")

        def preparar_y_fallar(i):
            preparar(i)
            raise OSError("COMMIT falló")
        return original(preparar=preparar_y_fallar, **kw)

    monkeypatch.setattr(app.state.cola, "crear_pieza", crear_y_fallar)
    with pytest.raises(OSError):
        subir(cliente)
    assert [p.name for p in config_tmp.carpeta_piezas.iterdir()] == []
