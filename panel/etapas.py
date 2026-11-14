"""Etapas reales del trabajo (Tarea 15): 3D y ficha.

Pendientes de sus tareas: SPZ (6), QR (13) y Reel (14). Sin SPZ, la etapa "3d" deja el
`pieza.ply` y `entrada.png` en el borrador.

Idol y Gemma no caben a la vez en la VRAM: la etapa "3d" libera el pipeline de Idol al
terminar (también si falla) y solo después corre "ficha". La ficha queda en
`ficha_borrador`; hasta que el dueño la apruebe no entra al sitio.
"""
from __future__ import annotations

from typing import Callable

from panel.cola import ContextoTrabajo, Etapa
from panel.config import Config
from panel.ficha import Ficha, redactar_ficha
from panel.idol import ParametrosIdol
from panel.lote import GeneradorIdol


class Etapa3D:
    nombre = "3d"

    def __init__(self, generador: GeneradorIdol, parametros: ParametrosIdol):
        self.generador, self.parametros = generador, parametros

    def __call__(self, ctx: ContextoTrabajo) -> None:
        foto = ctx.borrador / "foto.jpg"
        if not foto.is_file():
            raise FileNotFoundError("falta la foto limpia (borrador/foto.jpg)")
        try:
            self.generador.generar(foto, ctx.borrador, self.parametros)
        finally:
            self.generador.liberar()  # Gemma necesita la VRAM


class EtapaFicha:
    nombre = "ficha"

    def __init__(self, config: Config, redactar: Callable[..., Ficha]):
        self.config, self.redactar = config, redactar

    def __call__(self, ctx: ContextoTrabajo) -> None:
        ficha = self.redactar(ctx.borrador / "foto.jpg", url_ollama=self.config.url_ollama,
                              modelo=self.config.modelo_ficha)
        ctx.cola.guardar_ficha_borrador(ctx.pieza.id, ficha)


def etapas_reales(config: Config, *, generador: GeneradorIdol | None = None,
                  redactar: Callable[..., Ficha] = redactar_ficha) -> list[Etapa]:
    return [Etapa3D(generador or GeneradorIdol(),
                    ParametrosIdol(num_gaussians=config.num_gaussianos)),
            EtapaFicha(config, redactar)]
