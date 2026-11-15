"""Publicación en gh-pages (Tarea 19), siempre contra un repo bare local, nunca contra GitHub."""
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from panel.catalogo.publicar import ErrorPublicacion, publicar, publicar_sitio
from panel.cola import Cola
from panel.ficha import Ficha

RAIZ = Path(__file__).resolve().parent.parent


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def repo_bare(tmp_path):
    ruta = tmp_path / "remoto.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(ruta)], check=True, capture_output=True)
    return str(ruta)


def repo_local(tmp_path):
    ruta = tmp_path / "local"
    if not ruta.exists():
        subprocess.run(["git", "init", "-b", "main", str(ruta)], check=True, capture_output=True)
        git(ruta, "config", "user.name", "Persona de prueba")
        git(ruta, "config", "user.email", "prueba@example.com")
        (ruta / "LEEME.md").write_text("hola", encoding="utf-8")
        git(ruta, "add", "-A")
        git(ruta, "commit", "-m", "inicial")
    return ruta


def sitio_con(tmp_path, archivos):
    sitio = tmp_path / "sitio_fuente"
    shutil.rmtree(sitio, ignore_errors=True)
    sitio.mkdir()
    for a in archivos:
        (sitio / a).write_text(a, encoding="utf-8")
    return sitio


def test_rama_de_un_solo_commit(tmp_path):
    remoto = repo_bare(tmp_path)
    publicar_sitio(sitio_con(tmp_path, ["a.html", "b.html"]), repo_local(tmp_path), tmp_path / "t", remoto)
    publicar_sitio(sitio_con(tmp_path, ["a.html"]), repo_local(tmp_path), tmp_path / "t", remoto)
    assert git(remoto, "rev-list", "--count", "gh-pages") == "1"
    assert git(remoto, "ls-tree", "--name-only", "gh-pages").split() == ["a.html"]


def test_devuelve_el_sha_publicado(tmp_path):
    remoto = repo_bare(tmp_path)
    sha = publicar_sitio(sitio_con(tmp_path, ["a.html"]), repo_local(tmp_path), tmp_path / "t", remoto)
    assert sha == git(remoto, "rev-parse", "gh-pages")


def test_no_toca_main(tmp_path):
    remoto = repo_bare(tmp_path)
    local = repo_local(tmp_path)
    antes = (git(local, "rev-parse", "HEAD"), git(local, "status", "--porcelain"), git(local, "branch", "--list"))
    publicar_sitio(sitio_con(tmp_path, ["a.html"]), local, tmp_path / "t", remoto)
    assert (git(local, "rev-parse", "HEAD"), git(local, "status", "--porcelain"), git(local, "branch", "--list")) == antes
    assert not (local / "a.html").exists()


def test_error_de_git_lanza_error_publicacion(tmp_path):
    with pytest.raises(ErrorPublicacion):
        publicar_sitio(sitio_con(tmp_path, ["a.html"]), repo_local(tmp_path), tmp_path / "t",
                       str(tmp_path / "no_existe.git"))


def _aprobar(cola, nombre, slug):
    i = cola.crear_pieza()
    b = cola.carpeta_borrador(i)
    b.mkdir(parents=True)
    shutil.copy(RAIZ / "tests" / "fixtures" / "mini.spz", b / "pieza.spz")
    Image.new("RGB", (8, 8)).save(b / "portada.jpg")
    cola.guardar_ficha_borrador(i, Ficha(nombre, "Gres", "Cerámica", "x"))
    cola.fijar_slug(i, slug)
    cola.aplicar(i, "empezar"); cola.aplicar(i, "terminar")
    return i


@pytest.fixture
def config_pub(config_tmp):
    # `raiz` es tmp_path: necesita visor/ y node_modules/ para generar el sitio
    shutil.copytree(RAIZ / "visor", config_tmp.raiz / "visor")
    shutil.copytree(RAIZ / "node_modules" / "three", config_tmp.raiz / "node_modules" / "three")
    shutil.copytree(RAIZ / "node_modules" / "@sparkjsdev", config_tmp.raiz / "node_modules" / "@sparkjsdev")
    return config_tmp


def test_marca_publicadas(config_pub, tmp_path):
    cola = Cola(config_pub)
    a = _aprobar(cola, "Cuenco", "cuenco"); cola.aprobar(a)
    r = _aprobar(cola, "Jarra", "jarra"); cola.aprobar(r)
    cola.editar_ficha(r, Ficha("Jarra editada", "Gres", "Cerámica", "x"))   # vuelve a «para revisar» con vigente
    remoto = repo_bare(tmp_path)
    resultado = publicar(config_pub, cola, repo=repo_local(tmp_path), remoto=remoto)
    assert resultado["piezas"] == 2 and resultado["sha"] == git(remoto, "rev-parse", "gh-pages")
    assert resultado["url"] == config_pub.url_publica
    assert cola.obtener(a).estado.value == "publicada"
    assert cola.obtener(r).estado.value == "para revisar"
    cola.cerrar()


def test_verificacion_bloquea_push(config_pub, tmp_path):
    cola = Cola(config_pub)
    a = _aprobar(cola, "Cuenco", "cuenco"); cola.aprobar(a)
    exif = Image.Exif()
    exif[0x8825] = {1: "N"}
    Image.new("RGB", (8, 8)).save(cola.carpeta_vigente(a) / "portada.jpg", exif=exif)
    remoto = repo_bare(tmp_path)
    with pytest.raises(ErrorPublicacion, match="EXIF"):
        publicar(config_pub, cola, repo=repo_local(tmp_path), remoto=remoto)
    assert "gh-pages" not in git(remoto, "branch", "--list")
    assert cola.obtener(a).estado.value == "aprobada"
    cola.cerrar()
