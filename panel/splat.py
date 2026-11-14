"""PLY -> SPZ en Python puro, y el límite de 10 MB.

No hay binarios de `spz` (Niantic) para Windows y compilarlos exige Visual Studio, así que el
codificador está escrito aquí con numpy y gzip siguiendo `src/cc/load-spz.cc` del repositorio
nianticlabs/spz (commit d5abdee). Escribe la **versión 3** del formato (gzip, un solo flujo,
rotaciones «smallest three» de 4 bytes), que es la que leen Spark y las herramientas de Niantic.

Orientación: se guardan posiciones y rotaciones tal como vienen en el PLY, sin conversión de ejes.
Spark carga PLY y SPZ sin transformarlos, así que el visor aplica la misma rotación a los dos
(`visor.js`, `splat.quaternion.set(1, 0, 0, 0)`, ver docs/pico-idol.md).

Solo se guarda el color de grado 0 (`f_dc_*`): las gaussianas de Idol no traen armónicos esféricos.

Uso desde la terminal (no necesita la GPU):
    uv run python -m panel.splat CARPETA_O_PLY... [--limite-mb 10]
"""
from __future__ import annotations

import argparse
import gzip
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

MAGIC = 0x5053474E            # "NGSP"
VERSION = 3
BITS_FRACCIONALES = 12        # ~0,25 mm de resolución en posición
ESCALA_COLOR = 0.15           # colorScale de spz
RAIZ_MEDIO = 0.7071067811865476
LIMITE_SPZ = 10 * 1024 * 1024
CANTIDADES = (262_144, 131_072, 65_536)

_CAMPOS = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
           "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
# Para cada componente mayor del cuaternión (xyzw), los otros tres índices en orden ascendente.
_RESTO = np.array([[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]])


class SplatDemasiadoGrande(Exception):
    pass


@dataclass(frozen=True)
class InformeSplat:
    num_gaussianos: int
    bytes: int


@dataclass
class SpzLeido:
    num_gaussianos: int
    posiciones: np.ndarray
    colores: np.ndarray
    alfas: np.ndarray        # logit, como en el PLY
    escalas: np.ndarray      # logaritmo, como en el PLY
    rotaciones: np.ndarray   # xyzw


def _leer_ply(ply: Path) -> dict[str, np.ndarray]:
    """Lee un PLY binario little endian con propiedades `float`. Devuelve una columna por campo."""
    datos = Path(ply).read_bytes()
    fin = datos.find(b"end_header\n")
    if fin < 0:
        raise ValueError(f"{ply} no tiene 'end_header'")
    lineas = datos[:fin].decode("ascii", errors="replace").splitlines()
    if "format binary_little_endian 1.0" not in lineas:
        raise ValueError(f"{ply}: solo se admite binary_little_endian")
    n, nombres = None, []
    for linea in lineas:
        partes = linea.split()
        if partes[:2] == ["element", "vertex"]:
            n = int(partes[2])
        elif partes[:1] == ["property"]:
            if partes[1] != "float":
                raise ValueError(f"{ply}: la propiedad {partes[2]} no es float")
            nombres.append(partes[2])
    if n is None:
        raise ValueError(f"{ply} no tiene 'element vertex'")
    faltan = [c for c in _CAMPOS if c not in nombres]
    if faltan:
        raise ValueError(f"{ply}: faltan los campos {', '.join(faltan)}")
    tabla = np.frombuffer(datos, dtype="<f4", count=n * len(nombres), offset=fin + len("end_header\n"))
    tabla = tabla.reshape(n, len(nombres))
    return {c: tabla[:, nombres.index(c)] for c in _CAMPOS}


def _a_uint8(x: np.ndarray) -> np.ndarray:
    return np.clip(np.floor(x + 0.5), 0, 255).astype(np.uint8)


def _empaquetar_rotaciones(c: dict[str, np.ndarray]) -> np.ndarray:
    q = np.stack([c["rot_1"], c["rot_2"], c["rot_3"], c["rot_0"]], axis=1).astype(np.float32)  # xyzw
    norma = np.linalg.norm(q, axis=1, keepdims=True)
    q = np.where(norma > 0, q / np.where(norma > 0, norma, 1), np.array([0, 0, 0, 1], dtype=np.float32))
    mayor = np.abs(q).argmax(axis=1)
    fila = np.arange(len(q))
    negar = q[fila, mayor] < 0
    resto = np.take_along_axis(q, _RESTO[mayor], axis=1)
    negativos = (resto < 0) ^ negar[:, None]
    mag = np.minimum((511 * np.abs(resto) / np.float32(RAIZ_MEDIO) + np.float32(0.5)).astype(np.uint32), 511)
    comp = mayor.astype(np.uint32)
    for k in range(3):
        comp = (comp << 10) | (negativos[:, k].astype(np.uint32) << 9) | mag[:, k]
    return comp.astype("<u4").view(np.uint8).reshape(-1, 4)


def comprimir(ply: Path, destino: Path) -> int:
    """Convierte un PLY de gaussianas en un `.spz` (v3). Devuelve los bytes escritos."""
    c = _leer_ply(Path(ply))
    n = len(c["x"])
    pos = np.stack([c["x"], c["y"], c["z"]], axis=1).astype(np.float32) * np.float32(1 << BITS_FRACCIONALES)
    fijo = (np.sign(pos) * np.floor(np.abs(pos) + 0.5)).astype(np.int32)
    posiciones = np.stack([(fijo >> (8 * k)) & 0xFF for k in range(3)], axis=2).astype(np.uint8)  # (n, 3, 3)
    alfas = _a_uint8(1 / (1 + np.exp(-c["opacity"].astype(np.float64))) * 255)
    colores = _a_uint8(np.stack([c["f_dc_0"], c["f_dc_1"], c["f_dc_2"]], axis=1) * (ESCALA_COLOR * 255) + 127.5)
    escalas = _a_uint8((np.stack([c["scale_0"], c["scale_1"], c["scale_2"]], axis=1) + 10) * 16)
    cuerpo = b"".join(a.tobytes() for a in (posiciones, alfas, colores, escalas, _empaquetar_rotaciones(c)))
    cabecera = struct.pack("<IIIBBBB", MAGIC, VERSION, n, 0, BITS_FRACCIONALES, 0, 0)
    comprimido = gzip.compress(cabecera + cuerpo, compresslevel=9, mtime=0)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(comprimido)
    return len(comprimido)


def leer_spz(ruta: Path) -> SpzLeido:
    """Decodifica un `.spz` gzip (v2 o v3). Sirve para comprobar lo que escribe `comprimir`."""
    crudo = gzip.decompress(Path(ruta).read_bytes())
    magic, version, n, grado, bits, _flags, _ = struct.unpack("<IIIBBBB", crudo[:16])
    if magic != MAGIC or version not in (2, 3) or grado != 0:
        raise ValueError(f"{ruta}: no es un SPZ v2/v3 sin armónicos esféricos")
    o = 16

    def tomar(n_bytes: int) -> np.ndarray:
        nonlocal o
        a = np.frombuffer(crudo, dtype=np.uint8, count=n_bytes, offset=o)
        o += n_bytes
        return a

    b = tomar(n * 9).reshape(n, 3, 3).astype(np.int32)
    v = b[:, :, 0] | (b[:, :, 1] << 8) | (b[:, :, 2] << 16)
    v = np.where(v & 0x800000, v - (1 << 24), v)
    posiciones = v / float(1 << bits)
    a = np.clip(tomar(n).astype(np.float64) / 255, 1e-6, 1 - 1e-6)
    alfas = np.log(a / (1 - a))
    colores = ((tomar(n * 3).reshape(n, 3) / 255.0) - 0.5) / ESCALA_COLOR
    escalas = tomar(n * 3).reshape(n, 3) / 16.0 - 10
    if version == 3:
        comp = tomar(n * 4).view("<u4").astype(np.uint32).reshape(n)
        mayor = (comp >> 30).astype(int)
        q = np.zeros((n, 4))
        suma = np.zeros(n)
        for k in (2, 1, 0):                      # el último componente escrito está en los bits bajos
            mag, neg = comp & 511, (comp >> 9) & 1
            comp = comp >> 10
            val = RAIZ_MEDIO * mag / 511 * np.where(neg == 1, -1, 1)
            q[np.arange(n), _RESTO[mayor][:, k]] = val
            suma += val ** 2
        q[np.arange(n), mayor] = np.sqrt(np.maximum(0, 1 - suma))
    else:
        xyz = tomar(n * 3).reshape(n, 3) / 127.5 - 1
        q = np.concatenate([xyz, np.sqrt(np.maximum(0, 1 - (xyz ** 2).sum(axis=1, keepdims=True)))], axis=1)
    return SpzLeido(n, posiciones, colores, alfas, escalas, q)


def _mb(n: int) -> str:
    return f"{n / 1024 ** 2:.1f} MB"


def splat_dentro_del_limite(generar_ply: Callable[[int], Path], destino: Path, limite: int,
                            cantidades: tuple[int, ...] = CANTIDADES) -> InformeSplat:
    """Prueba las cantidades en orden y se queda con la primera cuyo `.spz` cabe en `limite`.

    `generar_ply(n)` produce el PLY con n gaussianos (en el panel, Idol). Si ninguna cabe lanza
    `SplatDemasiadoGrande` con los tamaños probados y no deja ningún `.spz` en `destino`.
    """
    destino = Path(destino)
    destino.unlink(missing_ok=True)   # un SPZ viejo no puede hacerse pasar por el de este intento
    temporal = destino.with_name(destino.name + ".tmp")
    tamanos: list[tuple[int, int]] = []
    for n in cantidades:
        peso = comprimir(generar_ply(n), temporal)
        if peso <= limite:
            os.replace(temporal, destino)
            return InformeSplat(num_gaussianos=n, bytes=peso)
        tamanos.append((n, peso))
    temporal.unlink(missing_ok=True)
    detalle = "; ".join(f"{n} gaussianos = {_mb(p)}" for n, p in tamanos)
    raise SplatDemasiadoGrande(f"el modelo supera el límite de {_mb(limite)} con todas las cantidades probadas: {detalle}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="panel.splat", description="PLY -> SPZ (pieza.ply -> pieza.spz).")
    ap.add_argument("rutas", nargs="+", type=Path, help="archivos .ply o carpetas con un pieza.ply")
    ap.add_argument("--limite-mb", type=float, default=LIMITE_SPZ / 1024 ** 2)
    args = ap.parse_args(argv)
    limite = int(args.limite_mb * 1024 ** 2)
    fuera = 0
    for ruta in args.rutas:
        ply = ruta / "pieza.ply" if ruta.is_dir() else ruta
        if not ply.is_file():
            print(f"ERR {ruta}: no hay PLY")
            fuera += 1
            continue
        spz = ply.with_suffix(".spz")
        peso = comprimir(ply, spz)
        if peso > limite:
            spz.unlink()
            fuera += 1
            print(f"AVISO {ply}: el SPZ pesa {_mb(peso)} y supera el límite de {_mb(limite)}; "
                  f"hay que regenerar el modelo con menos gaussianos (no se guardó el .spz)")
        else:
            print(f"OK  {ply}: PLY {_mb(ply.stat().st_size)} -> SPZ {_mb(peso)}")
    return 1 if fuera else 0


if __name__ == "__main__":
    sys.exit(main())
