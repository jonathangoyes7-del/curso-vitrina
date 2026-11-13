"""Pico de validación de Idol: uv run python scripts/pico_idol.py FOTO SALIDA

Genera SALIDA/pieza.ply y SALIDA/entrada.png, e imprime el tiempo y el pico de VRAM.
Usa el VAE de FLUX.2-klein-4B (Apache 2.0), nunca el de FLUX.2-dev (no comercial).
"""
import sys
import time
from pathlib import Path

import torch
from idol import IdolPipeline

VAE_COMERCIAL = "black-forest-labs/FLUX.2-klein-4B"


def main(foto: str, salida: str) -> None:
    salida_dir = Path(salida)
    salida_dir.mkdir(parents=True, exist_ok=True)
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    pipeline = IdolPipeline.from_pretrained(
        "speridlabs/idol",
        image_encoders={"flux2_vae": VAE_COMERCIAL},
        # Modo rápido: torch.compile con triton-windows (sin compilador de C++ extra).
        optimize=True,
    )
    t_carga = time.perf_counter() - t0
    t1 = time.perf_counter()
    salida_idol = pipeline(foto, mode="real", seed=42, num_gaussians=262_144)
    torch.cuda.synchronize()
    t_pieza = time.perf_counter() - t1
    salida_idol.gaussian.save_ply(str(salida_dir / "pieza.ply"))
    salida_idol.preprocessed_image.save(str(salida_dir / "entrada.png"))
    print(f"torch {torch.__version__} / CUDA {torch.version.cuda}")
    print(f"Carga del pipeline: {t_carga:.1f} s")
    print(f"Tiempo por pieza: {t_pieza:.1f} s")
    print(f"Pico de VRAM: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python scripts/pico_idol.py FOTO SALIDA")
    main(sys.argv[1], sys.argv[2])
