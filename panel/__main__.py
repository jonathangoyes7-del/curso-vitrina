"""Lanza el panel local: `iniciar.bat` (doble clic), `iniciar.ps1` o `uv run python -m panel`.

Solo escucha en 127.0.0.1 (no hay opción de host). Arranca también el trabajador de la cola:
un solo hilo que convierte cada foto subida en 3D, un trabajo a la vez.
"""
import logging
import socket
import threading
import webbrowser

import uvicorn

from panel.api import crear_app
from panel.config import Config
from panel.entorno import comprobar_entorno
from panel.etapas import etapas_reales

HOST = "127.0.0.1"
PUERTO = 8765


def puerto_ocupado(host: str, puerto: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex((host, puerto)) == 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    url = f"http://{HOST}:{PUERTO}/"
    if puerto_ocupado(HOST, PUERTO):
        # Segundo doble clic: el panel ya está abierto, solo se vuelve a mostrar.
        print(f"Vitrina ya está abierta en {url}. Se abre en el navegador.")
        webbrowser.open(url)
        return
    config = Config.por_defecto()
    print("Comprobando que todo está listo...")
    for parte in comprobar_entorno(config).values():
        print(("  [listo] " if parte["listo"] else "  [AVISO] ") + parte["mensaje"])
    print(f"\nVitrina está abierta en {url}\nNo cierres esta ventana mientras uses el panel.\n")
    app = crear_app(config, etapas_reales(config))
    threading.Timer(1.5, webbrowser.open, args=(url,)).start()  # da tiempo a que el servidor escuche
    uvicorn.run(app, host=HOST, port=PUERTO)


if __name__ == "__main__":
    main()
