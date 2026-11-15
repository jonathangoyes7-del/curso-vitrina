"""Publicación del sitio en la rama huérfana `gh-pages` (Tarea 19).

La rama tiene siempre un solo commit y se sube con `--force`. Se construye en una carpeta de trabajo
aparte (`datos/publicacion/`): nunca se toca la rama ni el árbol de trabajo del repo del proyecto.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from datetime import datetime
from pathlib import Path

from panel.catalogo.generador import generar_sitio, publicas_desde_cola, verificar_sitio
from panel.cola import Cola
from panel.config import Config


class ErrorPublicacion(Exception):
    pass


def _git(cwd: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise ErrorPublicacion(f"git {' '.join(args[:2])} falló: {(e.stderr or e.stdout).strip()}") from e
    except OSError as e:
        raise ErrorPublicacion(f"No se pudo ejecutar git: {e}") from e
    return r.stdout.strip()


def publicar_sitio(sitio: Path, repo: Path, trabajo: Path, remoto: str | None = None) -> str:
    sitio, repo, trabajo = Path(sitio), Path(repo), Path(trabajo)
    if not sitio.is_dir():
        raise ErrorPublicacion(f"No existe la carpeta del sitio: {sitio}")
    if remoto is None:
        remoto = _git(repo, "remote", "get-url", "origin")
    nombre = _git(repo, "config", "user.name")
    correo = _git(repo, "config", "user.email")

    if trabajo.exists():
        # En Windows los objetos de .git son de solo lectura: se les quita el atributo al borrar.
        shutil.rmtree(trabajo, onerror=lambda f, ruta, _: (os.chmod(ruta, stat.S_IWRITE), f(ruta)))
    shutil.copytree(sitio, trabajo)
    _git(trabajo, "init", "-b", "gh-pages")
    _git(trabajo, "add", "-A")
    _git(trabajo, "-c", f"user.name={nombre}", "-c", f"user.email={correo}",
         "commit", "-m", f"Publicación {datetime.now():%Y-%m-%d %H:%M}")
    sha = _git(trabajo, "rev-parse", "HEAD")
    _git(trabajo, "push", "--force", remoto, "gh-pages:gh-pages")
    return sha


def publicar(config: Config, cola: Cola, *, repo: Path | None = None, remoto: str | None = None) -> dict:
    """Genera, verifica y publica. Si la verificación falla no se hace push ni se cambia ningún estado."""
    piezas = publicas_desde_cola(cola)
    generar_sitio(piezas, config.sitio, config.raiz, config.url_publica)
    problemas = verificar_sitio(config.sitio, config.limite_spz, config.limite_pagina)
    if problemas:
        raise ErrorPublicacion("El sitio no pasa la verificación y no se publica:\n- " + "\n- ".join(problemas))
    sha = publicar_sitio(config.sitio, repo or config.raiz, config.datos / "publicacion", remoto)
    cola.marcar_publicadas()
    return {"sha": sha, "piezas": len(piezas), "url": config.url_publica}
