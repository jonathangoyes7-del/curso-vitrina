"""Compresión PLY -> SPZ en Python puro (no hay binarios de `spz` para Windows)."""
import gzip
import struct

import numpy as np
import pytest

from panel.idol import contar_gaussianos
from panel.splat import (InformeSplat, SplatDemasiadoGrande, comprimir, leer_spz,
                         splat_dentro_del_limite)
from tests.utilidades import escribir_ply_sintetico


def test_comprimir_conserva_cantidad(tmp_path):
    ply = escribir_ply_sintetico(tmp_path / "s.ply", 4096)
    assert comprimir(ply, tmp_path / "s.spz") > 0
    assert leer_spz(tmp_path / "s.spz").num_gaussianos == 4096


def test_cabecera_spz_v3(tmp_path):
    ply = escribir_ply_sintetico(tmp_path / "s.ply", 100)
    comprimir(ply, tmp_path / "s.spz")
    crudo = gzip.decompress((tmp_path / "s.spz").read_bytes())
    magic, version, n, grado, bits_frac, flags, _ = struct.unpack("<IIIBBBB", crudo[:16])
    assert (magic, version, n, grado, bits_frac, flags) == (0x5053474E, 3, 100, 0, 12, 0)
    assert len(crudo) == 16 + 100 * (9 + 1 + 3 + 3 + 4)


def test_ida_y_vuelta_conserva_los_valores(tmp_path):
    ply = escribir_ply_sintetico(tmp_path / "s.ply", 2000, radio=0.5)
    comprimir(ply, tmp_path / "s.spz")
    s = leer_spz(tmp_path / "s.spz")
    original = np.fromfile(ply, dtype="<f4", offset=ply.read_bytes().index(b"end_header\n") + 11).reshape(2000, 14)
    assert np.abs(s.posiciones - original[:, 0:3]).max() < 1 / 4096          # 12 bits fraccionales
    assert np.abs(s.colores - original[:, 3:6]).max() < 0.02                  # 8 bits sobre el color
    assert np.abs(s.alfas - original[:, 6]).max() < 0.2                       # logit de 2.0 -> alfa 8 bits
    assert np.abs(s.escalas - original[:, 7:10]).max() < 1 / 16               # (escala + 10) * 16
    assert np.abs(np.linalg.norm(s.rotaciones, axis=1) - 1).max() < 0.01      # cuaterniones unitarios


def test_rotaciones_se_reordenan_wxyz_a_xyzw(tmp_path):
    # El PLY guarda rot_0 = w; el SPZ guarda xyzw. Una rotación de 90° sobre Z no debe cambiar de eje.
    ply = escribir_ply_sintetico(tmp_path / "s.ply", 64, rotacion=(np.cos(np.pi / 4), 0, 0, np.sin(np.pi / 4)))
    comprimir(ply, tmp_path / "s.spz")
    q = leer_spz(tmp_path / "s.spz").rotaciones
    assert np.allclose(np.abs(q[0]), [0, 0, np.sin(np.pi / 4), np.cos(np.pi / 4)], atol=0.01)


def test_ply_sin_campos_falla(tmp_path):
    ply = tmp_path / "malo.ply"
    ply.write_bytes(b"ply\nformat binary_little_endian 1.0\nelement vertex 1\nproperty float x\nend_header\n" + bytes(4))
    with pytest.raises(ValueError, match="campos"):
        comprimir(ply, tmp_path / "m.spz")


def test_acepta_normales_y_campos_extra(tmp_path):
    # El PLY real de Idol trae nx, ny, nz entre las posiciones y el color.
    n = 50
    nombres = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
               "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
    datos = np.zeros((n, len(nombres)), dtype="<f4")
    datos[:, 0] = np.linspace(-0.5, 0.5, n)
    datos[:, 9] = 2.0
    datos[:, 13] = 1.0
    cab = f"ply\nformat binary_little_endian 1.0\nelement vertex {n}\n" + "".join(
        f"property float {c}\n" for c in nombres) + "end_header\n"
    ply = tmp_path / "idol.ply"
    ply.write_bytes(cab.encode() + datos.tobytes())
    comprimir(ply, tmp_path / "i.spz")
    s = leer_spz(tmp_path / "i.spz")
    assert s.num_gaussianos == n and np.abs(s.posiciones[:, 0] - datos[:, 0]).max() < 1 / 4096


def test_baja_gaussianos_si_no_cabe(tmp_path):
    pedidos = []

    def generar(n):
        pedidos.append(n)
        return escribir_ply_sintetico(tmp_path / f"{n}.ply", n // 64)

    t1 = comprimir(generar(262_144), tmp_path / "a.spz")
    t2 = comprimir(generar(131_072), tmp_path / "b.spz")
    pedidos.clear()
    inf = splat_dentro_del_limite(generar, tmp_path / "p.spz", limite=(t1 + t2) // 2)
    assert pedidos == [262_144, 131_072]
    assert inf == InformeSplat(num_gaussianos=131_072, bytes=t2)
    assert (tmp_path / "p.spz").stat().st_size == t2


def test_a_la_primera_si_cabe(tmp_path):
    pedidos = []

    def generar(n):
        pedidos.append(n)
        return escribir_ply_sintetico(tmp_path / f"{n}.ply", 256)

    inf = splat_dentro_del_limite(generar, tmp_path / "p.spz", limite=10 * 1024 * 1024)
    assert pedidos == [262_144] and inf.num_gaussianos == 262_144 and inf.bytes > 0


def test_ninguna_cabe(tmp_path):
    def generar_grande(n):
        return escribir_ply_sintetico(tmp_path / f"{n}.ply", 4096)

    with pytest.raises(SplatDemasiadoGrande) as e:
        splat_dentro_del_limite(generar_grande, tmp_path / "p.spz", limite=10)
    mensaje = str(e.value)
    assert all(str(n) in mensaje for n in (262144, 131072, 65536)) and "MB" in mensaje
    assert not (tmp_path / "p.spz").exists()


def test_el_ply_de_cada_intento_es_el_que_se_comprime(tmp_path):
    # El .spz final corresponde al último PLY generado, no a uno anterior.
    def generar(n):
        return escribir_ply_sintetico(tmp_path / f"{n}.ply", n // 64)

    t2 = comprimir(generar(131_072), tmp_path / "b.spz")
    inf = splat_dentro_del_limite(generar, tmp_path / "p.spz", limite=t2)
    assert inf.num_gaussianos == 131_072
    assert leer_spz(tmp_path / "p.spz").num_gaussianos == 131_072 // 64   # los puntos del PLY de 131 072


def test_contar_gaussianos_del_ply_sintetico(tmp_path):
    assert contar_gaussianos(escribir_ply_sintetico(tmp_path / "s.ply", 10)) == 10
