"""Página de créditos y licencias (Tarea 20 bis): modelos, librerías y fotos de Unsplash.

Las licencias se comprobaron el 2026-11-14 (metadatos de los paquetes instalados, fichas de
Hugging Face y `ollama show --license`). Si se añade o cambia un modelo o una librería, se
actualiza aquí; ante la duda sobre una licencia, se para y se pregunta.
"""
from __future__ import annotations

from dataclasses import dataclass

from panel.catalogo.modelos import PiezaPublica

APACHE = "https://www.apache.org/licenses/LICENSE-2.0"
MIT = "https://opensource.org/license/mit"
BSD3 = "https://opensource.org/license/bsd-3-clause"
URL_DINOV3 = "https://ai.meta.com/resources/models-and-libraries/dinov3-license"
URL_UNSPLASH = "https://unsplash.com/license"


@dataclass(frozen=True)
class Credito:
    nombre: str
    autoria: str
    licencia: str
    url_licencia: str
    uso: str


MODELOS = (
    Credito("Idol", "Speridlabs", "Apache 2.0", APACHE,
            "Convierte la foto de la pieza en un splat 3D."),
    Credito("DINOv3", "Meta", "Licencia DINOv3", URL_DINOV3,
            "Codificador de imagen del que depende Idol. Built with DINOv3."),
    Credito("VAE de FLUX.2-klein-4B", "Black Forest Labs", "Apache 2.0", APACHE,
            "Autocodificador de imagen que usa Idol."),
    Credito("Gemma 4 12B", "Google (ejecutado en local con Ollama)", "Apache 2.0", APACHE,
            "Redacta el borrador de la ficha, que siempre revisa una persona."),
)

LIBRERIAS_SITIO = (
    Credito("Three.js 0.186.0", "Autores de three.js", "MIT", MIT, "Muestra la pieza en 3D en el navegador."),
    Credito("Spark 2.4.0", "World Labs", "MIT", MIT, "Dibuja los splats gaussianos dentro de Three.js."),
)

LIBRERIAS_CONSTRUCCION = (
    Credito("PyTorch", "Equipo de PyTorch", "BSD-3", BSD3, "Ejecuta Idol en la GPU."),
    Credito("torchvision", "Equipo de PyTorch", "BSD-3", BSD3, "Utilidades de imagen para PyTorch."),
    Credito("FastAPI", "Sebastián Ramírez", "MIT", MIT, "Panel local."),
    Credito("Uvicorn", "Encode", "BSD-3", BSD3, "Servidor del panel local."),
    Credito("Jinja2", "Pallets", "BSD-3", BSD3, "Plantillas de las páginas del catálogo."),
    Credito("Pillow", "Jeffrey «Alex» Clark y colaboradores", "MIT-CMU", "https://opensource.org/license/mit-cmu",
            "Limpia las fotos y crea las portadas."),
    Credito("pillow-heif", "Alexander Piskun", "BSD-3", BSD3, "Lee fotos HEIC de móvil."),
    Credito("segno", "Lars Heuer", "BSD-3", BSD3, "Genera el código QR de cada pieza."),
    Credito("httpx", "Encode", "BSD-3", BSD3, "Cliente HTTP (Ollama y descargas)."),
    Credito("python-multipart", "Andrew Dunham y Marcelo Trylesinski", "Apache 2.0", APACHE,
            "Recibe las fotos que se suben al panel."),
    Credito("Playwright", "Microsoft", "Apache 2.0", APACHE, "Graba el Reel con el visor."),
    Credito("Formato SPZ", "Niantic", "MIT", MIT, "Formato comprimido de los splats."),
)


def renderizar_creditos(piezas: list[PiezaPublica]) -> str:
    from panel.catalogo.componente import entorno_plantillas
    return entorno_plantillas().get_template("creditos.html").render(
        raiz="../", modelos=MODELOS, librerias_sitio=LIBRERIAS_SITIO,
        librerias_construccion=LIBRERIAS_CONSTRUCCION, url_dinov3=URL_DINOV3, url_unsplash=URL_UNSPLASH,
        fotos=[p for p in piezas if p.es_ejemplo and p.credito_autor])
