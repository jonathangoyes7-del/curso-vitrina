from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from panel import lote
from panel.lote import GeneradorIdol, ResultadoIdol


class PipelineFalso:
    def __init__(self, fallar_con: str | None = None):
        self.kwargs = None
        self.fallar_con = fallar_con

    def __call__(self, foto, **kwargs):
        if self.fallar_con and self.fallar_con in str(foto):
            raise RuntimeError("falla simulada")
        self.kwargs = kwargs
        gaussian = SimpleNamespace(save_ply=lambda ruta: Path(ruta).write_bytes(b"ply"))
        imagen = SimpleNamespace(save=lambda ruta: Path(ruta).write_bytes(b"png"))
        return SimpleNamespace(gaussian=gaussian, preprocessed_image=imagen)


def foto_falsa(tmp_path, i=0, nombre=None):
    ruta = tmp_path / "fotos" / (nombre or f"f{i}.jpg")
    ruta.parent.mkdir(exist_ok=True)
    Image.new("RGB", (8, 8)).save(ruta)
    return ruta


def test_carga_una_sola_vez(tmp_path):
    llamadas = []
    gen = GeneradorIdol(fabrica=lambda: llamadas.append(1) or PipelineFalso())
    for i in range(3):
        gen.generar(foto_falsa(tmp_path, i), tmp_path / f"s{i}")
    assert len(llamadas) == 1


def test_pasa_parametros(tmp_path):
    p = PipelineFalso()
    GeneradorIdol(fabrica=lambda: p).generar(foto_falsa(tmp_path), tmp_path / "s")
    assert p.kwargs["mode"] == "real" and p.kwargs["num_gaussians"] == 262_144


def test_escribe_ply_y_entrada(tmp_path):
    gen = GeneradorIdol(fabrica=PipelineFalso)
    foto = foto_falsa(tmp_path)
    r = gen.generar(foto, tmp_path / "s")
    assert isinstance(r, ResultadoIdol)
    assert r.ply == tmp_path / "s" / "pieza.ply" and r.ply.exists()
    assert r.entrada == tmp_path / "s" / "entrada.png" and r.entrada.exists()


def test_liberar_recarga(tmp_path, monkeypatch):
    monkeypatch.setattr(lote, "_vaciar_cuda", lambda: None)
    llamadas = []
    gen = GeneradorIdol(fabrica=lambda: llamadas.append(1) or PipelineFalso())
    gen.generar(foto_falsa(tmp_path, 0), tmp_path / "a")
    gen.liberar()
    gen.generar(foto_falsa(tmp_path, 1), tmp_path / "b")
    assert len(llamadas) == 2


def test_cli_sigue_tras_fallo(tmp_path, monkeypatch):
    entrada = tmp_path / "in"
    entrada.mkdir()
    for n in ("a.jpg", "b.jpg", "c.png"):
        Image.new("RGB", (8, 8)).save(entrada / n)
    (entrada / "notas.txt").write_text("no es imagen")
    pipeline = PipelineFalso(fallar_con="b.jpg")
    monkeypatch.setattr(lote, "_fabrica_por_defecto", lambda: pipeline)
    monkeypatch.setattr(lote, "_vaciar_cuda", lambda: None)
    salida = tmp_path / "out"
    codigo = lote.main([str(entrada), str(salida)])
    assert codigo == 1
    assert (salida / "a" / "pieza.ply").exists()
    assert (salida / "c" / "pieza.ply").exists()
    assert not (salida / "b" / "pieza.ply").exists()


def test_cli_todo_bien_devuelve_0(tmp_path, monkeypatch):
    entrada = tmp_path / "in"
    entrada.mkdir()
    Image.new("RGB", (8, 8)).save(entrada / "a.jpg")
    monkeypatch.setattr(lote, "_fabrica_por_defecto", lambda: PipelineFalso())
    monkeypatch.setattr(lote, "_vaciar_cuda", lambda: None)
    assert lote.main([str(entrada), str(tmp_path / "out")]) == 0


def test_cli_rechaza_num_gaussianos_invalido(tmp_path):
    with pytest.raises(SystemExit):
        lote.main([str(tmp_path), str(tmp_path / "o"), "--num-gaussianos", "100"])
