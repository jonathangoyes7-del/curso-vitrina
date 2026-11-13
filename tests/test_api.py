import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter

from panel.api import crear_app

H = {"X-Vitrina": "panel"}
FIXTURE = Path(__file__).parent / "fixtures" / "fotos" / "ceramica.jpg"


@pytest.fixture
def app(config_tmp):
    return crear_app(config_tmp)


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
    carpeta = config_tmp.carpeta_piezas / r.json()["id"]
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
                      "error": None, "es_ejemplo": True}]
    det = cliente.get(f"/api/piezas/{i}").json()
    assert det["archivos"]["foto.jpg"] == f"/api/piezas/{i}/archivos/foto.jpg"
    assert "pieza.spz" not in det["archivos"]
    assert cliente.get(f"/api/piezas/{'0' * 32}").status_code == 404


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
