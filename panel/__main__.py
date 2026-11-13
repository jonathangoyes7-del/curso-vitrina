"""Lanza el panel local: `uv run python -m panel` (solo 127.0.0.1).

Arranca también el trabajador de la cola: un solo hilo que convierte cada foto subida
en 3D, un trabajo a la vez.
"""
import logging

import uvicorn

from panel.api import crear_app
from panel.config import Config

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    config = Config.por_defecto()
    uvicorn.run(crear_app(config), host=config.host, port=config.puerto)
