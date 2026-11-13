from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    datos: Path
    sitio: Path
    raiz: Path
    host: str = "127.0.0.1"
    puerto: int = 8765
    url_publica: str = "https://jonathangoyes7-del.github.io/curso-vitrina/"
    url_ollama: str = "http://127.0.0.1:11434"
    modelo_ficha: str = "gemma4:12b"
    num_gaussianos: int = 262_144
    limite_spz: int = 10 * 1024 * 1024
    limite_pagina: int = 500 * 1024

    @classmethod
    def por_defecto(cls) -> "Config":
        raiz = Path(__file__).resolve().parent.parent
        return cls(datos=raiz / "datos", sitio=raiz / "sitio", raiz=raiz)

    @property
    def carpeta_piezas(self) -> Path:
        return self.datos / "piezas"
