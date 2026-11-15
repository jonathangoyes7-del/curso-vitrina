"""Comprobaciones al arrancar: ¿están listos Ollama y la tarjeta gráfica?

Cada comprobación devuelve `{"listo": bool, "mensaje": str}` con un texto pensado para quien usa
el panel (sin jerga). Nunca lanza: un fallo se cuenta en el mensaje.
"""
from __future__ import annotations

import httpx

from panel.config import Config


def comprobar_ollama(config: Config, *, espera: float = 2.0) -> dict:
    url = config.url_ollama.rstrip("/")
    try:
        r = httpx.get(f"{url}/api/tags", timeout=espera)
        r.raise_for_status()
        modelos = [m.get("name", "") for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return {"listo": False, "mensaje": (
            "Ollama está apagado o no responde. Ábrelo (el icono de la llama junto al reloj, o desde el "
            "menú Inicio) y pulsa «Volver a comprobar». Sin Ollama las piezas se quedan sin ficha.")}
    modelo = config.modelo_ficha
    if not any(m == modelo or m.split(":")[0] == modelo for m in modelos):
        return {"listo": False, "mensaje": (
            f"Ollama está encendido, pero falta el modelo de las fichas. Descárgalo con: "
            f"ollama pull {modelo}")}
    return {"listo": True, "mensaje": f"Ollama listo (modelo {modelo})."}


def comprobar_gpu() -> dict:
    try:
        import torch  # se importa aquí: tarda unos segundos y no hace falta antes
        if not torch.cuda.is_available():
            return {"listo": False, "mensaje": (
                "No se detecta la tarjeta gráfica (CUDA). Sin ella no se pueden crear los modelos 3D. "
                "Comprueba los controladores de NVIDIA y reinicia el equipo.")}
        return {"listo": True, "mensaje": f"Tarjeta gráfica lista: {torch.cuda.get_device_name(0)}."}
    except Exception as exc:  # torch ausente o roto: se cuenta, no se rompe el arranque
        return {"listo": False, "mensaje": (
            f"No se pudo comprobar la tarjeta gráfica ({type(exc).__name__}). "
            "Vuelve a ejecutar instalar.ps1.")}


def comprobar_entorno(config: Config) -> dict:
    return {"ollama": comprobar_ollama(config), "gpu": comprobar_gpu()}
