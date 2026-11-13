"""Generador de Idol (foto -> PLY) y su CLI por lotes.

`idol` y `torch` se importan dentro de las funciones para que los tests no necesiten la GPU.
Usa el VAE de FLUX.2-klein-4B (Apache 2.0).
"""
import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from panel.idol import ParametrosIdol, validar_num_gaussianos

log = logging.getLogger("panel.lote")

VAE_COMERCIAL = "black-forest-labs/FLUX.2-klein-4B"
EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class ResultadoIdol:
    ply: Path
    entrada: Path


def _fabrica_por_defecto() -> Any:
    from idol import IdolPipeline

    return IdolPipeline.from_pretrained(
        "speridlabs/idol",
        image_encoders={"flux2_vae": VAE_COMERCIAL},
        optimize=True,
    )


def _vaciar_cuda() -> None:
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _reiniciar_pico_vram() -> None:
    import torch

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def _pico_vram_gb() -> float:
    import torch

    if not torch.cuda.is_available():
        return 0.0
    torch.cuda.synchronize()
    return torch.cuda.max_memory_allocated() / 1024**3


class GeneradorIdol:
    def __init__(self, fabrica: Callable[[], Any] | None = None):
        self._fabrica = fabrica or _fabrica_por_defecto
        self._pipeline: Any = None

    def _cargar(self) -> Any:
        if self._pipeline is None:
            log.info("cargando pipeline")
            self._pipeline = self._fabrica()
        return self._pipeline

    def generar(self, foto: Path, carpeta: Path,
                parametros: ParametrosIdol = ParametrosIdol()) -> ResultadoIdol:
        pipeline = self._cargar()
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        salida = pipeline(str(foto), **parametros.como_kwargs())
        ply, entrada = carpeta / "pieza.ply", carpeta / "entrada.png"
        salida.gaussian.save_ply(str(ply))
        salida.preprocessed_image.save(str(entrada))
        return ResultadoIdol(ply=ply, entrada=entrada)

    def liberar(self) -> None:
        self._pipeline = None
        import gc

        gc.collect()
        _vaciar_cuda()


def _listar_fotos(entrada: Path) -> list[Path]:
    return sorted(p for p in entrada.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="panel.lote", description="Idol por lotes: foto -> PLY.")
    ap.add_argument("entrada", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--num-gaussianos", type=int, default=ParametrosIdol().num_gaussians)
    args = ap.parse_args(argv)
    try:
        validar_num_gaussianos(args.num_gaussianos)
    except ValueError as e:
        ap.error(str(e))
    if not args.entrada.is_dir():
        ap.error(f"{args.entrada} no es una carpeta")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parametros = ParametrosIdol(num_gaussians=args.num_gaussianos)
    generador = GeneradorIdol()
    fotos = _listar_fotos(args.entrada)
    if fotos:  # carga única, fuera de la medición de cada foto
        t_carga = time.perf_counter()
        generador._cargar()
        print(f"Carga del pipeline: {time.perf_counter() - t_carga:.1f} s")
    resumen: list[tuple[str, bool, float, str, float, int]] = []
    for foto in fotos:
        _reiniciar_pico_vram()
        t0 = time.perf_counter()
        try:
            r = generador.generar(foto, args.salida / foto.stem, parametros)
            seg, peso, error, ok = time.perf_counter() - t0, r.ply.stat().st_size, "", True
        except Exception as e:  # una foto rota no detiene el lote
            seg, peso, error, ok = time.perf_counter() - t0, 0, f"{type(e).__name__}: {e}", False
        resumen.append((foto.name, ok, seg, error, _pico_vram_gb(), peso))
    generador.liberar()

    for nombre, ok, seg, error, vram, peso in resumen:
        print(f"{'OK ' if ok else 'ERR'} {nombre}  {seg:.1f} s  VRAM pico {vram:.2f} GB  "
              f"PLY {peso / 1024**2:.1f} MB  {error}")
    fallos = sum(1 for r in resumen if not r[1])
    print(f"{len(resumen) - fallos} generadas, {fallos} con error")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
