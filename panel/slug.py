"""Slug estable de cada pieza y su dirección pública (Tarea 13)."""
from __future__ import annotations

import re
import threading
import unicodedata

from panel.cola import Cola

_CERROJO = threading.Lock()  # el trabajador y el panel pueden pedir slug a la vez: que no repartan el mismo
_LARGO_MAXIMO = 60


def crear_slug(nombre: str, ocupados: set[str]) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", nombre) if not unicodedata.combining(c))
    base = re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")[:_LARGO_MAXIMO].strip("-") or "pieza"
    slug, n = base, 2
    while slug in ocupados:
        slug = f"{base}-{n}"
        n += 1
    return slug


def asegurar_slug(cola: Cola, id: int) -> str:
    """Devuelve el slug de la pieza; si aún no está aprobada lo recalcula con su nombre actual.

    Una vez aprobada el slug no cambia (rompería QR impresos e `<iframe>` ajenos). Si una pieza
    aprobada no llegó a tener slug, se calcula con el nombre que se aprobó, no con el del borrador.
    """
    with _CERROJO:
        p = cola.obtener(id)
        if p.slug_fijo and p.slug:
            return p.slug
        ficha = (p.ficha_vigente if p.slug_fijo else None) or p.ficha_borrador
        ocupados = {o.slug for o in cola.listar() if o.id != id and o.slug}
        slug = crear_slug(ficha.nombre if ficha else "", ocupados)
        if p.slug != slug:
            cola.fijar_slug(id, slug)
        return slug


def url_pieza(url_publica: str, slug: str) -> str:
    return f"{url_publica}piezas/{slug}/"
