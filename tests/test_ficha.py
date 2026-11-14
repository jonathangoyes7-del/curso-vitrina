import json
from pathlib import Path

import httpx
import pytest

from panel.ficha import CATEGORIAS, Ficha, FichaInvalida, redactar_ficha, validar_ficha

FIXTURES = Path(__file__).parent / "fixtures" / "fotos"
VALIDA = {"nombre": "Cuenco de gres", "materiales": "Gres, esmalte mate",
          "categoria": "Cerámica", "cuidados": "Lavar a mano."}


class ClienteFalso(httpx.Client):
    def __init__(self, respuestas):
        self.peticiones = []
        pendientes = list(respuestas)

        def responder(req: httpx.Request) -> httpx.Response:
            self.peticiones.append(json.loads(req.content))
            r = pendientes.pop(0)
            contenido = r if isinstance(r, str) else json.dumps(r)
            return httpx.Response(200, json={"message": {"role": "assistant", "content": contenido}})

        super().__init__(transport=httpx.MockTransport(responder))


def foto(tmp_path: Path) -> Path:
    destino = tmp_path / "foto.jpg"
    destino.write_bytes((FIXTURES / "ceramica.jpg").read_bytes())
    return destino


def test_redacta_ficha_valida(tmp_path):
    cli = ClienteFalso([VALIDA])
    f = redactar_ficha(foto(tmp_path), url_ollama="http://x", modelo="gemma4:12b", cliente=cli)
    assert f.categoria == "Cerámica"
    cuerpo = cli.peticiones[0]
    assert cuerpo["model"] == "gemma4:12b" and cuerpo["keep_alive"] == 0
    assert cuerpo["stream"] is False and cuerpo["options"]["temperature"] == 0.2
    assert cuerpo["format"]["properties"]["categoria"]["enum"] == list(CATEGORIAS)
    assert cuerpo["messages"][-1]["images"][0]


def test_reintenta_una_vez_y_acepta(tmp_path):
    cli = ClienteFalso(["esto no es json", VALIDA])
    f = redactar_ficha(foto(tmp_path), url_ollama="http://x", modelo="m", cliente=cli)
    assert f.nombre == "Cuenco de gres" and len(cli.peticiones) == 2


def test_categoria_invalida_reintenta_y_falla(tmp_path):
    cli = ClienteFalso([{**VALIDA, "categoria": "Vidrio"}, "esto no es json"])
    with pytest.raises(FichaInvalida):
        redactar_ficha(foto(tmp_path), url_ollama="http://x", modelo="m", cliente=cli)
    assert len(cli.peticiones) == 2


def test_validar_ficha_errores():
    with pytest.raises(FichaInvalida) as e:
        validar_ficha({"nombre": " ", "materiales": "x", "categoria": "Otra", "cuidados": "y"})
    assert set(e.value.errores) == {"nombre", "categoria"}


def test_validar_ficha_recorta_y_limita():
    f = validar_ficha({**VALIDA, "nombre": "  Cuenco  "})
    assert f.nombre == "Cuenco"
    with pytest.raises(FichaInvalida) as e:
        validar_ficha({**VALIDA, "nombre": "x" * 81, "cuidados": "y" * 601})
    assert set(e.value.errores) == {"nombre", "cuidados"}
    with pytest.raises(FichaInvalida):
        validar_ficha({"nombre": "a"})  # faltan campos


def test_ficha_ida_y_vuelta():
    f = validar_ficha(VALIDA)
    assert Ficha.desde_dict(f.a_dict()) == f


@pytest.mark.ollama
def test_gemma_real():
    f = redactar_ficha(FIXTURES / "ceramica.jpg", url_ollama="http://127.0.0.1:11434", modelo="gemma4:12b")
    print(f)
    assert f.categoria in CATEGORIAS


def test_el_tono_se_lee_del_archivo_sin_el_comentario(tmp_path):
    from panel.ficha import construir_prompt
    tono = tmp_path / "tono.md"
    tono.write_text("<!-- nota para la dueña -->\nHabla bajito.", encoding="utf-8")
    prompt = construir_prompt(tono)
    assert "Habla bajito." in prompt
    assert "nota para la dueña" not in prompt
