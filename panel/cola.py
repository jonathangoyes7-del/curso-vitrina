"""Cola de trabajos con SQLite y un único trabajador (un trabajo a la vez).

Idol y Gemma no pueden compartir la VRAM: por eso solo hay un hilo que procesa,
y `tomar_siguiente` pasa la pieza a `procesando` de forma atómica.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Protocol

from panel.config import Config
from panel.ficha import Ficha
from panel.progreso import Progreso

log = logging.getLogger("panel.cola")


class Estado(StrEnum):
    PENDIENTE = "pendiente"
    PROCESANDO = "procesando"
    PARA_REVISAR = "para revisar"
    APROBADA = "aprobada"
    PUBLICADA = "publicada"
    DESPUBLICADA = "despublicada"
    ERROR = "error"


class TransicionInvalida(Exception):
    pass


_TABLA: dict[Estado, dict[str, Estado]] = {
    Estado.PENDIENTE: {"empezar": Estado.PROCESANDO},
    Estado.PROCESANDO: {"terminar": Estado.PARA_REVISAR, "fallar": Estado.ERROR},
    Estado.ERROR: {"reintentar": Estado.PENDIENTE},
    Estado.PARA_REVISAR: {"aprobar": Estado.APROBADA, "editar": Estado.PARA_REVISAR,
                          "reprocesar": Estado.PENDIENTE},
    Estado.APROBADA: {"publicar": Estado.PUBLICADA, "editar": Estado.PARA_REVISAR,
                      "reprocesar": Estado.PENDIENTE, "despublicar": Estado.DESPUBLICADA},
    Estado.PUBLICADA: {"editar": Estado.PARA_REVISAR, "reprocesar": Estado.PENDIENTE,
                       "despublicar": Estado.DESPUBLICADA},
    # aprobar desde despublicada exige versión vigente: lo comprueba Cola.aprobar.
    Estado.DESPUBLICADA: {"aprobar": Estado.APROBADA, "editar": Estado.PARA_REVISAR,
                          "reprocesar": Estado.PENDIENTE},
}


def transicion(estado: Estado, evento: str) -> Estado:
    try:
        return _TABLA[Estado(estado)][evento]
    except KeyError:
        raise TransicionInvalida(f"No se puede «{evento}» una pieza en estado «{estado}»") from None


@dataclass
class Pieza:
    id: int
    slug: str | None
    slug_fijo: bool
    estado: Estado
    ficha_borrador: Ficha | None
    ficha_vigente: Ficha | None
    en_sitio: bool
    es_ejemplo: bool
    credito_autor: str | None
    credito_url: str | None
    error: str | None
    creada: str
    actualizada: str


_ESQUEMA = """
CREATE TABLE IF NOT EXISTS piezas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT,
    slug_fijo INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL,
    ficha_borrador TEXT,
    ficha_vigente TEXT,
    en_sitio INTEGER NOT NULL DEFAULT 0,
    es_ejemplo INTEGER NOT NULL DEFAULT 0,
    credito_autor TEXT,
    credito_url TEXT,
    error TEXT,
    creada TEXT NOT NULL,
    actualizada TEXT NOT NULL,
    etapa TEXT,
    etapa_indice INTEGER NOT NULL DEFAULT 0,
    etapas_total INTEGER NOT NULL DEFAULT 0,
    etapa_fraccion REAL NOT NULL DEFAULT 0
)
"""

_COLUMNAS_PROGRESO = {
    "etapa": "TEXT",
    "etapa_indice": "INTEGER NOT NULL DEFAULT 0",
    "etapas_total": "INTEGER NOT NULL DEFAULT 0",
    "etapa_fraccion": "REAL NOT NULL DEFAULT 0",
}
_SIN_PROGRESO = {"etapa": None, "etapa_indice": 0, "etapas_total": 0, "etapa_fraccion": 0.0}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ficha(texto: str | None) -> Ficha | None:
    return None if texto is None else Ficha.desde_dict(json.loads(texto))


class Cola:
    def __init__(self, config: Config):
        self.config = config
        config.datos.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(config.datos / "vitrina.sqlite", check_same_thread=False,
                                   isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA busy_timeout = 5000")
            self._db.execute(_ESQUEMA)
            existentes = {f["name"] for f in self._db.execute("PRAGMA table_info(piezas)")}
            for nombre, tipo in _COLUMNAS_PROGRESO.items():  # migración de bases anteriores
                if nombre not in existentes:
                    self._db.execute(f"ALTER TABLE piezas ADD COLUMN {nombre} {tipo}")
        # Cambios para el flujo de eventos: cada escritura sube la versión y despierta a quien espera.
        self._cambios = threading.Condition()
        self._version = 0

    def version(self) -> int:
        with self._cambios:
            return self._version

    def esperar_cambio(self, desde: int, timeout: float) -> int:
        with self._cambios:
            if self._version == desde:
                self._cambios.wait(timeout)
            return self._version

    def _notificar(self) -> None:
        with self._cambios:
            self._version += 1
            self._cambios.notify_all()

    # --- utilidades internas -------------------------------------------------
    def _fila(self, id: int) -> sqlite3.Row:
        fila = self._db.execute("SELECT * FROM piezas WHERE id = ?", (id,)).fetchone()
        if fila is None:
            raise KeyError(id)
        return fila

    @staticmethod
    def _pieza(f: sqlite3.Row) -> Pieza:
        return Pieza(
            id=f["id"], slug=f["slug"], slug_fijo=bool(f["slug_fijo"]), estado=Estado(f["estado"]),
            ficha_borrador=_ficha(f["ficha_borrador"]), ficha_vigente=_ficha(f["ficha_vigente"]),
            en_sitio=bool(f["en_sitio"]), es_ejemplo=bool(f["es_ejemplo"]),
            credito_autor=f["credito_autor"], credito_url=f["credito_url"], error=f["error"],
            creada=f["creada"], actualizada=f["actualizada"])

    def _cambiar(self, id: int, evento: str, **extra: Any) -> Estado:
        """Aplica `evento` con UPDATE … WHERE estado = ? (atómico). Hay que tener el lock."""
        actual = Estado(self._fila(id)["estado"])
        nuevo = transicion(actual, evento)
        reinicia = evento in ("reintentar", "reprocesar", "empezar")
        columnas = {"estado": nuevo.value, "actualizada": _ahora(),
                    **(_SIN_PROGRESO if reinicia else {}), **extra}
        asignaciones = ", ".join(f"{k} = ?" for k in columnas)
        cur = self._db.execute(f"UPDATE piezas SET {asignaciones} WHERE id = ? AND estado = ?",
                               (*columnas.values(), id, actual.value))
        if cur.rowcount != 1:
            raise TransicionInvalida(f"La pieza {id} cambió de estado mientras se aplicaba «{evento}»")
        self._notificar()
        return nuevo

    # --- API pública ----------------------------------------------------------
    def crear_pieza(self, *, es_ejemplo: bool = False, credito_autor: str | None = None,
                    credito_url: str | None = None,
                    preparar: Callable[[int], None] | None = None) -> int:
        """Crea la pieza en `pendiente`.

        `preparar(id)` corre dentro de la misma transacción: el trabajador no ve la pieza
        hasta que sus archivos están en disco, y si `preparar` falla no queda la fila.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                ahora = _ahora()
                cur = self._db.execute(
                    "INSERT INTO piezas (estado, es_ejemplo, credito_autor, credito_url, creada,"
                    " actualizada) VALUES (?, ?, ?, ?, ?, ?)",
                    (Estado.PENDIENTE.value, int(es_ejemplo), credito_autor, credito_url, ahora, ahora))
                id = cur.lastrowid
                if preparar is not None:
                    preparar(id)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._notificar()
            return id

    def obtener(self, id: int) -> Pieza:
        with self._lock:
            return self._pieza(self._fila(id))

    def listar(self) -> list[Pieza]:
        with self._lock:
            filas = self._db.execute("SELECT * FROM piezas ORDER BY id DESC").fetchall()
        return [self._pieza(f) for f in filas]

    def aplicar(self, id: int, evento: str) -> Estado:
        with self._lock:
            extra = {"error": None} if evento == "reintentar" else {}
            return self._cambiar(id, evento, **extra)

    def guardar_ficha_borrador(self, id: int, ficha: Ficha) -> None:
        """Guarda la ficha del borrador sin cambiar el estado (lo usa la etapa de la ficha)."""
        with self._lock:
            cur = self._db.execute("UPDATE piezas SET ficha_borrador = ?, actualizada = ? WHERE id = ?",
                                   (json.dumps(ficha.a_dict(), ensure_ascii=False), _ahora(), id))
            if cur.rowcount != 1:
                raise KeyError(id)
        self._notificar()

    def editar_ficha(self, id: int, ficha: Ficha) -> Estado:
        """Guarda la ficha editada y aplica «editar»; si el estado no lo admite, no guarda nada."""
        with self._lock:
            return self._cambiar(id, "editar", ficha_borrador=json.dumps(ficha.a_dict(), ensure_ascii=False))

    def fijar_slug(self, id: int, slug: str) -> None:
        with self._lock:
            f = self._fila(id)
            if f["slug_fijo"] and f["slug"] != slug:
                raise TransicionInvalida(f"El slug de la pieza {id} ya está fijo")
            self._db.execute("UPDATE piezas SET slug = ?, actualizada = ? WHERE id = ?",
                             (slug, _ahora(), id))

    def tomar_siguiente(self) -> Pieza | None:
        with self._lock:
            fila = self._db.execute("SELECT id FROM piezas WHERE estado = ? ORDER BY id LIMIT 1",
                                    (Estado.PENDIENTE.value,)).fetchone()
            if fila is None:
                return None
            self._cambiar(fila["id"], "empezar", error=None)
            return self._pieza(self._fila(fila["id"]))

    def marcar_error(self, id: int, mensaje: str) -> None:
        with self._lock:
            self._cambiar(id, "fallar", error=mensaje)

    def recuperar_interrumpidos(self) -> int:
        with self._lock:
            cur = self._db.execute("UPDATE piezas SET estado = ?, actualizada = ?, etapa = NULL, etapa_indice = 0,"
                " etapas_total = 0, etapa_fraccion = 0 WHERE estado = ?",
                (Estado.PENDIENTE.value, _ahora(), Estado.PROCESANDO.value))
        self._notificar()
        return cur.rowcount

    def aprobar(self, id: int) -> None:
        with self._lock:
            f = self._fila(id)
            vigente = self.carpeta_vigente(id)
            if Estado(f["estado"]) is Estado.DESPUBLICADA:
                if not (vigente / "pieza.spz").is_file():
                    raise TransicionInvalida(f"La pieza {id} no tiene versión vigente")
                self._cambiar(id, "aprobar", en_sitio=1)
                return
            transicion(Estado(f["estado"]), "aprobar")  # valida antes de tocar archivos
            if vigente.exists():
                shutil.rmtree(vigente)
            shutil.copytree(self.carpeta_borrador(id), vigente,
                            ignore=shutil.ignore_patterns("pieza.ply"))
            self._cambiar(id, "aprobar", ficha_vigente=f["ficha_borrador"], en_sitio=1, slug_fijo=1)

    def despublicar(self, id: int) -> None:
        with self._lock:
            self._cambiar(id, "despublicar", en_sitio=0)

    def marcar_publicadas(self) -> int:
        with self._lock:
            cur = self._db.execute(
                "UPDATE piezas SET estado = ?, actualizada = ? WHERE estado = ? AND en_sitio = 1",
                (Estado.PUBLICADA.value, _ahora(), Estado.APROBADA.value))
        self._notificar()
        return cur.rowcount

    def piezas_para_sitio(self) -> list[Pieza]:
        with self._lock:
            filas = self._db.execute("SELECT * FROM piezas WHERE en_sitio = 1 ORDER BY id").fetchall()
        return [self._pieza(f) for f in filas
                if (self.carpeta_vigente(f["id"]) / "pieza.spz").is_file()]

    def borrar(self, id: int) -> None:
        with self._lock:
            if Estado(self._fila(id)["estado"]) is Estado.PROCESANDO:
                raise TransicionInvalida(f"La pieza {id} se está procesando")
            self._db.execute("DELETE FROM piezas WHERE id = ?", (id,))
            shutil.rmtree(self.config.carpeta_piezas / str(id), ignore_errors=True)
        self._notificar()

    def registrar_progreso(self, id: int, etapa: str | None, indice: int, total: int,
                           fraccion: float) -> None:
        with self._lock:
            cur = self._db.execute(
                "UPDATE piezas SET etapa = ?, etapa_indice = ?, etapas_total = ?,"
                " etapa_fraccion = ?, actualizada = ? WHERE id = ?",
                (etapa, indice, total, fraccion, _ahora(), id))
            if cur.rowcount != 1:
                raise KeyError(id)
        self._notificar()

    def progreso(self, id: int) -> Progreso:
        with self._lock:
            f = self._fila(id)
        return Progreso(estado=Estado(f["estado"]), etapa=f["etapa"], indice=f["etapa_indice"],
                        total=f["etapas_total"], fraccion=f["etapa_fraccion"])

    def carpeta_borrador(self, id: int) -> Path:
        return self.config.carpeta_piezas / str(id) / "borrador"

    def carpeta_vigente(self, id: int) -> Path:
        return self.config.carpeta_piezas / str(id) / "vigente"

    def cerrar(self) -> None:
        with self._lock:
            self._db.close()


@dataclass
class ContextoTrabajo:
    pieza: Pieza
    borrador: Path
    cola: Cola
    informar: Callable[[float], None] = field(default=lambda fraccion: None)


class Etapa(Protocol):
    nombre: str

    def __call__(self, ctx: ContextoTrabajo) -> None: ...


class _CandadoInstancia:
    """Candado de archivo en datos/vitrina.lock: un solo panel procesa la cola.

    El sistema operativo lo suelta si el proceso muere, así que no queda bloqueado.
    """

    def __init__(self, ruta: Path):
        self.ruta = ruta
        self._fd: int | None = None

    def tomar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.ruta, os.O_RDWR | os.O_CREAT)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise RuntimeError(
                "Ya hay otro panel en marcha con estos datos; ciérralo antes de abrir otro") from None
        self._fd = fd

    def soltar(self) -> None:
        if self._fd is None:
            return
        if os.name == "nt":
            import msvcrt
            os.lseek(self._fd, 0, os.SEEK_SET)
            msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
        os.close(self._fd)  # en POSIX, cerrar suelta el flock
        self._fd = None


class Trabajador:
    """Un solo hilo que procesa la cola: un trabajo a la vez."""

    def __init__(self, cola: Cola, etapas: list[Etapa]):
        self.cola = cola
        self.etapas = list(etapas)
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._candado = _CandadoInstancia(cola.config.datos / "vitrina.lock")

    def procesar_uno(self) -> bool:
        pieza = self.cola.tomar_siguiente()
        if pieza is None:
            return False
        borrador = self.cola.carpeta_borrador(pieza.id)
        borrador.mkdir(parents=True, exist_ok=True)
        ctx = ContextoTrabajo(pieza=pieza, borrador=borrador, cola=self.cola)
        total = len(self.etapas)
        for i, etapa in enumerate(self.etapas):
            try:
                log.info("pieza %s: etapa %s", pieza.id, etapa.nombre)
                self.cola.registrar_progreso(pieza.id, etapa.nombre, i, total, 0.0)
                ctx.informar = lambda f, _n=etapa.nombre, _i=i: self.cola.registrar_progreso(
                    pieza.id, _n, _i, total, min(max(f, 0.0), 1.0))
                etapa(ctx)
            except Exception as exc:
                log.exception("pieza %s: falló la etapa %s", pieza.id, etapa.nombre)
                self.cola.marcar_error(pieza.id, f"{etapa.nombre}: {exc}")
                return True
        self.cola.aplicar(pieza.id, "terminar")
        log.info("pieza %s: lista para revisar", pieza.id)
        return True

    def _bucle(self) -> None:
        n = self.cola.recuperar_interrumpidos()
        if n:
            log.info("%s pieza(s) interrumpida(s) vuelven a pendiente", n)
        while not self._parar.is_set():
            try:
                hubo = self.procesar_uno()
            except Exception:
                log.exception("error inesperado en el trabajador")
                hubo = False
            if not hubo:
                self._parar.wait(1)

    def iniciar(self) -> None:
        if self._hilo is not None:
            if self._hilo.is_alive():
                # Puede seguir vivo tras un detener() que no esperó al final del trabajo:
                # nunca se lanza un segundo hilo.
                self._parar.clear()
                return
            self._hilo = None
        # Antes de recuperar_interrumpidos: otro panel podría estar procesando.
        self._candado.tomar()
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name="trabajador", daemon=True)
        self._hilo.start()

    def detener(self, espera: float | None = 5) -> None:
        self._parar.set()
        if self._hilo is None:
            return
        self._hilo.join(espera)
        if self._hilo.is_alive():
            log.warning("el trabajador sigue con un trabajo; se detendrá al terminarlo")
            return
        self._hilo = None
        self._candado.soltar()
