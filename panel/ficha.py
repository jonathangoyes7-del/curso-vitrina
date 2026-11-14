"""Ficha de una pieza: validación y redacción con Gemma (Ollama), en castellano."""
from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

CATEGORIAS = ("Cerámica", "Madera tallada", "Tejidos de lana")
_CAMPOS = ("nombre", "materiales", "categoria", "cuidados")
_LIMITES = {"nombre": 80, "materiales": 600, "categoria": 600, "cuidados": 600}


@dataclass(frozen=True)
class Ficha:
    nombre: str
    materiales: str
    categoria: str
    cuidados: str

    def a_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def desde_dict(cls, d: dict) -> "Ficha":
        return cls(**{c: d[c] for c in _CAMPOS})


class FichaInvalida(ValueError):
    def __init__(self, errores: dict[str, str]):
        self.errores = errores
        super().__init__("; ".join(f"{c}: {m}" for c, m in errores.items()))


def validar_ficha(datos: dict) -> Ficha:
    if not isinstance(datos, dict):
        raise FichaInvalida({c: "la ficha debe ser un objeto" for c in _CAMPOS})
    errores: dict[str, str] = {}
    limpios: dict[str, str] = {}
    for campo in _CAMPOS:
        valor = datos.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            errores[campo] = "es obligatorio"
            continue
        valor = valor.strip()
        if len(valor) > _LIMITES[campo]:
            errores[campo] = f"admite como máximo {_LIMITES[campo]} caracteres"
        elif campo == "categoria" and valor not in CATEGORIAS:
            errores[campo] = f"debe ser una de: {', '.join(CATEGORIAS)}"
        limpios[campo] = valor
    if errores:
        raise FichaInvalida(errores)
    return Ficha(**limpios)


_ESQUEMA = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string"},
        "materiales": {"type": "string"},
        "categoria": {"type": "string", "enum": list(CATEGORIAS)},
        "cuidados": {"type": "string"},
    },
    "required": list(_CAMPOS),
}

_PROMPT = (
    "Eres quien redacta las fichas de un catálogo de artesanía. Mira la foto de la pieza y "
    "escribe, en castellano, una ficha JSON con cuatro campos: "
    "«nombre» (corto, máximo 80 caracteres), «materiales» (de qué parece estar hecha), "
    f"«categoria» (exactamente una de: {', '.join(CATEGORIAS)}) y "
    "«cuidados» (consejos de limpieza y conservación adecuados al material). "
    "Describe solo lo que se ve en la foto: no inventes materiales, medidas, autores ni "
    "procedencia. Si dudas del material, dilo con prudencia («parece…»). Cada texto, "
    "como máximo 600 caracteres."
)


def redactar_ficha(foto: Path, *, url_ollama: str, modelo: str,
                   cliente: httpx.Client | None = None) -> Ficha:
    imagen = base64.b64encode(Path(foto).read_bytes()).decode("ascii")
    cuerpo = {
        "model": modelo,
        "stream": False,
        "keep_alive": 0,  # libera la VRAM para Idol
        "options": {"temperature": 0.2},
        "format": _ESQUEMA,
        "messages": [{"role": "user", "content": _PROMPT, "images": [imagen]}],
    }
    propio = cliente is None
    cli = cliente or httpx.Client(timeout=300)
    try:
        ultimo: FichaInvalida | None = None
        for _ in range(2):  # un intento y un reintento
            resp = cli.post(f"{url_ollama.rstrip('/')}/api/chat", json=cuerpo)
            resp.raise_for_status()
            try:
                return validar_ficha(json.loads(resp.json()["message"]["content"]))
            except (json.JSONDecodeError, KeyError, TypeError):
                ultimo = FichaInvalida({"respuesta": "Gemma no devolvió un JSON válido"})
            except FichaInvalida as exc:
                ultimo = exc
        raise ultimo
    finally:
        if propio:
            cli.close()
