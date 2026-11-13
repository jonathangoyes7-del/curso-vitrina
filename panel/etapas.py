"""Etapas reales del trabajo (Tarea 15, por ahora solo la de 3D).

Pendiente para sus tareas: SPZ (6), ficha (7), QR (13) y Reel (14). Cuando entre la
ficha, la etapa "3d" tendrá que llamar a `generador.liberar()` en un `finally` para que
Gemma tenga la VRAM libre; hasta entonces el pipeline de Idol se carga una sola vez y
se queda en memoria entre trabajos.
"""
from __future__ import annotations

from panel.cola import ContextoTrabajo, Etapa
from panel.config import Config
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
        self.generador.generar(foto, ctx.borrador, self.parametros)


def etapas_reales(config: Config, *, generador: GeneradorIdol | None = None) -> list[Etapa]:
    return [Etapa3D(generador or GeneradorIdol(),
                    ParametrosIdol(num_gaussians=config.num_gaussianos))]
