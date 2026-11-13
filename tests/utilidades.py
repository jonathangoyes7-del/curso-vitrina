"""Ayudas compartidas por los tests."""
from pathlib import Path

import numpy as np

CAMPOS = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
          "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]


def escribir_ply_sintetico(ruta: Path, n: int, radio: float = 0.5) -> Path:
    """PLY 3DGS binario (float32) con n puntos sobre una esfera de radio `radio`."""
    rng = np.random.default_rng(0)
    p = rng.normal(size=(n, 3))
    p = p / np.linalg.norm(p, axis=1, keepdims=True) * radio
    datos = np.zeros((n, len(CAMPOS)), dtype="<f4")
    datos[:, 0:3] = p
    datos[:, 3:6] = rng.uniform(-1, 1, size=(n, 3))   # color
    datos[:, 6] = 2.0                                  # opacidad (logit)
    datos[:, 7:10] = np.log(0.01)                      # escala (log)
    datos[:, 10] = 1.0                                 # cuaternión identidad
    cabecera = "ply\nformat binary_little_endian 1.0\n"
    cabecera += f"element vertex {n}\n"
    cabecera += "".join(f"property float {c}\n" for c in CAMPOS)
    cabecera += "end_header\n"
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(cabecera.encode("ascii"))
        f.write(datos.tobytes())
    return ruta
