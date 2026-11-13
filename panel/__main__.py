"""Lanza el panel local: `uv run python -m panel` (solo 127.0.0.1)."""
import uvicorn

from panel.api import crear_app
from panel.config import Config

if __name__ == "__main__":
    config = Config.por_defecto()
    uvicorn.run(crear_app(config), host=config.host, port=config.puerto)
