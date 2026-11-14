"""Ayudas compartidas por los tests."""
from pathlib import Path

import numpy as np

CAMPOS = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
          "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]


def escribir_ply_sintetico(ruta: Path, n: int, radio: float = 0.5,
                           rotacion: tuple = (1.0, 0.0, 0.0, 0.0)) -> Path:
    """PLY 3DGS binario (float32) con n puntos sobre una esfera de radio `radio`.

    `rotacion` es (w, x, y, z), como rot_0..rot_3 del PLY."""
    rng = np.random.default_rng(0)
    p = rng.normal(size=(n, 3))
    p = p / np.linalg.norm(p, axis=1, keepdims=True) * radio
    datos = np.zeros((n, len(CAMPOS)), dtype="<f4")
    datos[:, 0:3] = p
    datos[:, 3:6] = rng.uniform(-1, 1, size=(n, 3))   # color
    datos[:, 6] = 2.0                                  # opacidad (logit)
    datos[:, 7:10] = np.log(0.01)                      # escala (log)
    datos[:, 10:14] = rotacion                         # cuaternión (w, x, y, z)
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


def varianza_de_pixeles(png: bytes) -> float:
    """Varianza de la luminosidad de una captura PNG (0 = imagen plana)."""
    import io

    from PIL import Image
    gris = np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype="float64")
    return float(gris.var())


def escribir_spz_sintetico(ruta: Path, n: int = 3000, radio: float = 0.4) -> Path:
    """SPZ v2 (gzip) con n gaussianos sobre una esfera de colores. Sin la librería `spz`.

    Formato: cabecera de 16 bytes (magic, versión, n, grado SH, bits fraccionales, flags, reservado),
    luego posiciones (24 bits), alfas, colores, escalas y rotaciones (3 bytes), todo gzip.
    """
    import gzip
    import struct

    rng = np.random.default_rng(1)
    p = rng.normal(size=(n, 3))
    p = p / np.linalg.norm(p, axis=1, keepdims=True) * radio
    bits = 12
    fijo = np.round(p * (1 << bits)).astype(np.int32)
    pos = np.zeros((n, 3, 3), dtype=np.uint8)
    for k in range(3):
        v = fijo & 0xFFFFFF
        pos[:, :, k] = (v >> (8 * k)) & 0xFF
    alfas = np.full(n, 230, dtype=np.uint8)
    color = np.clip(np.round((p / radio * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)  # degradado por posición
    escala = np.full((n, 3), round((np.log(0.03) + 10) * 16), dtype=np.uint8)
    rot = np.full((n, 3), 128, dtype=np.uint8)  # cuaternión identidad (xyz = 0)
    cuerpo = b"".join(a.tobytes() for a in (pos, alfas, color, escala, rot))
    cabecera = struct.pack("<IIIBBBB", 0x5053474E, 2, n, 0, bits, 0, 0)
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(gzip.compress(cabecera + cuerpo))
    return ruta
