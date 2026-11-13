"""Mide la calidad de Idol: uv run python scripts/calidad_idol.py FOTO [SALIDA]

Genera la misma foto con distintos `num_gaussians` (131 072, 262 144, 524 288) y con
distintos `steps` (25 y 50, a 262 144 gaussianos), y escribe en docs/calidad-idol.md
las tablas con segundos, pico de VRAM y tamaño del PLY. Los PLY quedan en SALIDA
(por defecto datos/calidad/, fuera de Git). Hace una pasada de calentamiento sin
medir para no cargar la compilación de torch.compile en la primera fila.
"""
import dataclasses
import sys
import time
from pathlib import Path

import torch
from idol import IdolPipeline

from panel.idol import ParametrosIdol, contar_gaussianos, validar_num_gaussianos

VAE_COMERCIAL = "black-forest-labs/FLUX.2-klein-4B"
RAIZ = Path(__file__).resolve().parent.parent
DOC = RAIZ / "docs" / "calidad-idol.md"
INI, FIN = "<!-- tablas:inicio -->", "<!-- tablas:fin -->"

# Las tablas fijan sus propios valores, no dependen de los por defecto.
BASE = ParametrosIdol(num_gaussians=262_144, steps=50)
GAUSSIANOS = (131_072, 262_144, 524_288)
PASOS = (25, 50)


def medir(pipeline, foto: str, params: ParametrosIdol, destino: Path) -> dict:
    validar_num_gaussianos(params.num_gaussians)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    salida = pipeline(foto, **params.como_kwargs())
    torch.cuda.synchronize()
    segundos = time.perf_counter() - t0
    vram = torch.cuda.max_memory_allocated() / 1024**3
    salida.gaussian.save_ply(str(destino))
    return {
        "params": params,
        "segundos": segundos,
        "vram": vram,
        "mb": destino.stat().st_size / 1024**2,
        "gaussianos": contar_gaussianos(destino),
    }


def tabla(titulo: str, filas: list[dict], columna: str) -> str:
    campo = "steps" if columna == "Pasos" else "num_gaussians"
    out = [f"### {titulo}", "",
           f"| {columna} | Segundos | Pico de VRAM (GB) | PLY (MB) | Gaussianos en el PLY |",
           "|---:|---:|---:|---:|---:|"]
    for f in filas:
        valor = f"{getattr(f['params'], campo):,}".replace(",", " ")
        n = f"{f['gaussianos']:,}".replace(",", " ")
        out.append(f"| {valor} | {f['segundos']:.1f} | {f['vram']:.2f} | {f['mb']:.1f} | {n} |")
    return "\n".join(out)


def escribir_doc(contenido: str) -> None:
    texto = DOC.read_text(encoding="utf-8") if DOC.exists() else f"# Calidad de Idol\n\n{INI}\n{FIN}\n"
    if INI not in texto:
        texto += f"\n{INI}\n{FIN}\n"
    antes, resto = texto.split(INI, 1)
    despues = resto.split(FIN, 1)[1]
    DOC.write_text(f"{antes}{INI}\n{contenido}\n{FIN}{despues}", encoding="utf-8")


def main(foto: str, salida: str | None) -> None:
    carpeta = Path(salida) if salida else RAIZ / "datos" / "calidad"
    carpeta.mkdir(parents=True, exist_ok=True)
    pipeline = IdolPipeline.from_pretrained(
        "speridlabs/idol", image_encoders={"flux2_vae": VAE_COMERCIAL}, optimize=True)

    print("Calentamiento (sin medir)...", flush=True)
    pipeline(foto, **BASE.como_kwargs())

    cache: dict[tuple, dict] = {}

    def correr(**cambios) -> dict:
        p = dataclasses.replace(BASE, **cambios)
        clave = (p.num_gaussians, p.steps)
        if clave not in cache:
            nombre = f"g{p.num_gaussians}_s{p.steps}.ply"
            print(f"Midiendo {nombre}...", flush=True)
            cache[clave] = medir(pipeline, foto, p, carpeta / nombre)
        return cache[clave]

    por_gaussianos = [correr(num_gaussians=n) for n in GAUSSIANOS]
    por_pasos = [correr(steps=s) for s in PASOS]

    escribir_doc("\n\n".join([
        f"Foto: `{Path(foto).name}`, `mode=\"real\"`, `seed=42`, `cfg_strength=3.0`, "
        f"medido con `optimize=True` tras un calentamiento.",
        tabla("Gaussianos (pasos = 50)", por_gaussianos, "Gaussianos"),
        tabla("Pasos (gaussianos = 262 144)", por_pasos, "Pasos"),
    ]))
    print(f"Tablas escritas en {DOC}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("Uso: python scripts/calidad_idol.py FOTO [SALIDA]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
