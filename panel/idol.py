"""Parámetros de calidad de Idol y utilidades sobre el PLY."""
from dataclasses import asdict, dataclass
from pathlib import Path

MIN_GAUSSIANOS = 32_768
MAX_GAUSSIANOS = 1_048_576
MULTIPLO = 32


@dataclass(frozen=True)
class ParametrosIdol:
    mode: str = "real"
    num_gaussians: int = 262_144
    steps: int = 25
    seed: int = 42
    cfg_strength: float = 3.0

    def como_kwargs(self) -> dict:
        return asdict(self)


def validar_num_gaussianos(n: int) -> int:
    """Devuelve n si está en [32 768, 1 048 576] y es múltiplo de 32; si no, ValueError."""
    if not MIN_GAUSSIANOS <= n <= MAX_GAUSSIANOS:
        raise ValueError(f"num_gaussians {n} fuera de [{MIN_GAUSSIANOS}, {MAX_GAUSSIANOS}]")
    if n % MULTIPLO:
        raise ValueError(f"num_gaussians {n} no es múltiplo de {MULTIPLO}")
    return n


def contar_gaussianos(ply: Path) -> int:
    """Lee `element vertex N` de la cabecera del PLY."""
    with open(ply, "rb") as f:
        for linea in f:
            texto = linea.decode("ascii", errors="replace").strip()
            if texto.startswith("element vertex"):
                return int(texto.split()[2])
            if texto == "end_header":
                break
    raise ValueError(f"{ply} no tiene 'element vertex' en la cabecera")
