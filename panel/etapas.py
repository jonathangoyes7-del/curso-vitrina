"""Etapas reales del trabajo (Tarea 15): 3D, ficha y QR.

Pendiente de su tarea: Reel (14). La etapa "3d" deja `pieza.spz` (≤ límite, ver
`panel.splat`), el `pieza.ply` del último intento y `entrada.png` en el borrador. Si ni con
65 536 gaussianos cabe en el límite, la pieza pasa a `error` con los tamaños probados.

Idol y Gemma no caben a la vez en la VRAM: la etapa "3d" libera el pipeline de Idol al
terminar (también si falla) y solo después corre "ficha". La ficha queda en
`ficha_borrador`; hasta que el dueño la apruebe no entra al sitio.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable

from panel.cola import ContextoTrabajo, Etapa
from panel.config import Config
from panel.ficha import Ficha, redactar_ficha
from panel.idol import MIN_GAUSSIANOS, ParametrosIdol
from panel.lote import GeneradorIdol
from panel.qr import refrescar_qr
from panel.splat import splat_dentro_del_limite

log = logging.getLogger("panel.etapas")


class Etapa3D:
    nombre = "3d"

    def __init__(self, generador: GeneradorIdol, parametros: ParametrosIdol, limite_spz: int):
        self.generador, self.parametros, self.limite_spz = generador, parametros, limite_spz

    def __call__(self, ctx: ContextoTrabajo) -> None:
        foto = ctx.borrador / "foto.jpg"
        if not foto.is_file():
            raise FileNotFoundError("falta la foto limpia (borrador/foto.jpg)")
        n0 = self.parametros.num_gaussians
        cantidades = tuple(n for n in (n0, n0 // 2, n0 // 4) if n >= MIN_GAUSSIANOS)

        def generar_ply(n: int):
            return self.generador.generar(foto, ctx.borrador, replace(self.parametros, num_gaussians=n)).ply

        try:
            informe = splat_dentro_del_limite(generar_ply, ctx.borrador / "pieza.spz", self.limite_spz,
                                              cantidades)
            log.info("pieza %s: pieza.spz con %d gaussianos, %d bytes", ctx.pieza.id,
                     informe.num_gaussianos, informe.bytes)
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


class EtapaQR:
    nombre = "qr"

    def __call__(self, ctx: ContextoTrabajo) -> None:
        # Asigna el slug a partir del nombre de la ficha y deja qr.svg y qr.png en el borrador.
        refrescar_qr(ctx.cola, ctx.pieza.id)


def etapas_reales(config: Config, *, generador: GeneradorIdol | None = None,
                  redactar: Callable[..., Ficha] = redactar_ficha) -> list[Etapa]:
    return [Etapa3D(generador or GeneradorIdol(),
                    ParametrosIdol(num_gaussians=config.num_gaussianos), config.limite_spz),
            EtapaFicha(config, redactar), EtapaQR()]
