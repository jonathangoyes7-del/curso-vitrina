import pytest

from panel.config import Config


@pytest.fixture
def config_tmp(tmp_path):
    """Config con `datos` y `sitio` dentro de tmp_path."""
    return Config(
        datos=tmp_path / "datos",
        sitio=tmp_path / "sitio",
        raiz=tmp_path,
    )
