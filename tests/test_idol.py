import pytest

from panel.idol import ParametrosIdol, contar_gaussianos, validar_num_gaussianos
from tests.utilidades import escribir_ply_sintetico


def test_validar_num_gaussianos():
    assert validar_num_gaussianos(262_144) == 262_144
    for malo in (32_736, 1_048_608, 262_145):
        with pytest.raises(ValueError):
            validar_num_gaussianos(malo)


def test_contar_gaussianos(tmp_path):
    ply = escribir_ply_sintetico(tmp_path / "s.ply", 4096)
    assert contar_gaussianos(ply) == 4096


def test_parametros_por_defecto():
    assert ParametrosIdol().como_kwargs() == {"mode": "real", "num_gaussians": 262_144,
        "steps": 25, "seed": 42, "cfg_strength": 3.0}
