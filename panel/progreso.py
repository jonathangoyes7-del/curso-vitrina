"""Progreso de cada trabajo, errores legibles y flujo de eventos del servidor (SSE)."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterator

if TYPE_CHECKING:  # evita el import circular con panel.cola
    from panel.cola import Cola, Estado

ETIQUETAS_ETAPA = {
    "3d": "Creando el modelo 3D",
    "spz": "Comprimiendo el modelo",
    "ficha": "Escribiendo la ficha",
    "qr": "Generando el QR",
    "reel": "Grabando el Reel",
}
_NOMBRE_ETAPA = {
    "3d": "del modelo 3D", "spz": "de la compresión", "ficha": "de la ficha",
    "qr": "del QR", "reel": "del Reel",
}


@dataclass
class Progreso:
    estado: "Estado"
    etapa: str | None
    indice: int
    total: int
    fraccion: float

    @property
    def porcentaje(self) -> int:
        if str(self.estado) not in ("pendiente", "procesando", "error"):
            return 100
        if self.total == 0:
            return 0
        return round(100 * (self.indice + self.fraccion) / self.total)

    @property
    def etapa_texto(self) -> str | None:
        return None if self.etapa is None else ETIQUETAS_ETAPA.get(self.etapa, self.etapa)


def explicar_error(error: str | None) -> dict | None:
    """Convierte «etapa: mensaje técnico» en algo que entienda quien usa el panel."""
    if not error:
        return None
    etapa, _, detalle = error.partition(": ")
    if not detalle:
        etapa, detalle = "", error
    bajo = error.lower()
    donde = _NOMBRE_ETAPA.get(etapa, "")
    if "supera el límite" in bajo:
        titulo = "El modelo 3D pesa demasiado para publicarlo"
        sugerencia = ("Ni con menos detalle cabe en el límite de peso. Prueba con otra foto (fondo liso, "
                      "pieza más simple) y vuelve a procesarla.")
    elif "out of memory" in bajo or "vram" in bajo:
        titulo = "La tarjeta gráfica se quedó sin memoria"
        sugerencia = "Cierra los programas que usen la GPU (juegos, otros modelos) y pulsa «Reintentar»."
    elif "connection" in bajo or "11434" in bajo or "ollama" in bajo:
        titulo = "No se pudo hablar con Ollama"
        sugerencia = "Comprueba que Ollama está abierto y que el modelo está descargado; luego «Reintentar»."
    elif "foto" in bajo and ("falta" in bajo or "no such file" in bajo):
        titulo = "Falta la foto de la pieza"
        sugerencia = "Elimina esta pieza y súbela de nuevo."
    elif "json" in bajo or "categor" in bajo:
        titulo = "La IA no devolvió una ficha válida"
        sugerencia = "Suele arreglarse al reintentar. Si se repite, edita la ficha a mano."
    else:
        titulo = f"Falló la creación {donde}".strip() if donde else "Falló el procesamiento"
        sugerencia = "Pulsa «Reintentar». Si vuelve a fallar, avisa con el detalle técnico."
    return {"titulo": titulo, "detalle": detalle, "sugerencia": sugerencia, "tecnico": error}


def _evento(nombre: str, datos) -> str:
    return f"event: {nombre}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


def flujo_eventos(cola: "Cola", instantanea: Callable[[], list], parar: threading.Event, *,
                  latido: float = 15.0, sondeo: float = 1.0) -> Iterator[str]:
    """Genera texto SSE: una foto del estado al conectar y otra cada vez que algo cambia.

    No hay sondeo desde el navegador: el hilo espera en la cola y despierta al instante
    cuando el trabajador o la API cambian algo. Cada `latido` s sin cambios manda un
    comentario para mantener viva la conexión; `sondeo` es solo cuánto tarda en notar `parar`.
    """
    yield "retry: 3000\n\n"
    visto = cola.version()
    yield _evento("piezas", instantanea())
    ultimo_envio = time.monotonic()
    while not parar.is_set():
        nueva = cola.esperar_cambio(visto, sondeo)
        if parar.is_set():
            break
        if nueva != visto:
            visto = nueva
            yield _evento("piezas", instantanea())
            ultimo_envio = time.monotonic()
        elif time.monotonic() - ultimo_envio >= latido:
            yield ": latido\n\n"
            ultimo_envio = time.monotonic()
