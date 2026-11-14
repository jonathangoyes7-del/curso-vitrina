"""API local del panel (Tarea 9, conectada a la cola; con corregir ficha y aprobar)."""
from __future__ import annotations

import shutil
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, Form, Header, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from panel.cola import Cola, Etapa, Pieza, Trabajador, TransicionInvalida
from panel.config import Config
from panel.ficha import FichaInvalida, validar_ficha
from panel.fotos import completar_miniaturas, crear_miniaturas, crear_portada, limpiar_foto, revisar_foto
from panel.progreso import explicar_error, flujo_eventos

ARCHIVOS_PERMITIDOS = {
    "foto.jpg": "image/jpeg",
    "portada.jpg": "image/jpeg",
    "lista.jpg": "image/jpeg",     # miniatura para la lista del panel
    "ficha.jpg": "image/jpeg",     # miniatura para la ficha
    "entrada.png": "image/png",
    "pieza.spz": "application/octet-stream",
    "pieza.ply": "application/octet-stream",   # el original de Idol; el visor lo usa mientras no exista el SPZ
    "qr.svg": "image/svg+xml",
    "reel.mp4": "video/mp4",
}
EXTENSIONES_ORIGINAL = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def _no_encontrada() -> JSONResponse:
    return JSONResponse({"detail": "No encontrada"}, status_code=404)


def _id(texto: str) -> int | None:
    # Hasta 18 cifras: cabe en el INTEGER de SQLite (los ids reales son pequeños).
    return int(texto) if texto.isascii() and texto.isdigit() and len(texto) <= 18 else None


def _nombre(p: Pieza) -> str | None:
    return p.ficha_borrador.nombre if p.ficha_borrador else None


def crear_app(config: Config, etapas: list[Etapa] | None = None,
              iniciar_trabajador: bool = True) -> FastAPI:
    # Pendiente para sus tareas: el parámetro `publicar` y las rutas despublicar,
    # reprocesar, borrar y publicar.
    if etapas is None:
        from panel.etapas import etapas_reales
        etapas = etapas_reales(config)
    cola = Cola(config)
    completar_miniaturas(config.carpeta_piezas)  # las piezas anteriores a las miniaturas también las tienen
    trabajador = Trabajador(cola, etapas)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        if iniciar_trabajador:
            trabajador.iniciar()
        try:
            yield
        finally:
            app.state.parar_eventos.set()  # cierra los flujos SSE abiertos para poder apagar
            trabajador.detener()

    def cabecera_para_docs(x_vitrina: str = Header("panel", alias="X-Vitrina")) -> None:
        # Solo para que «Try it out» de /docs envíe la cabecera en todas las rutas; la exige el middleware.
        return None

    app = FastAPI(title="Vitrina: panel local", lifespan=ciclo_de_vida,
                  dependencies=[Depends(cabecera_para_docs)])
    app.state.config = config
    app.state.cola = cola
    app.state.trabajador = trabajador
    app.state.parar_eventos = threading.Event()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def exigir_cabecera(request, call_next):
        if request.method not in METODOS_SEGUROS and request.headers.get("x-vitrina") != "panel":
            return JSONResponse({"detail": "Falta la cabecera X-Vitrina: panel"}, status_code=403)
        return await call_next(request)

    def pieza(texto: str) -> Pieza | None:
        id_ = _id(texto)
        if id_ is None:
            return None
        try:
            return cola.obtener(id_)
        except KeyError:
            return None

    def resumen(p: Pieza) -> dict:
        pr = cola.progreso(p.id)
        return {"id": p.id, "slug": p.slug, "estado": p.estado.value, "nombre": _nombre(p),
                "error": p.error, "es_ejemplo": p.es_ejemplo,
                "etapa": pr.etapa, "etapa_texto": pr.etapa_texto, "porcentaje": pr.porcentaje,
                "error_legible": explicar_error(p.error),
                "puede_reintentar": p.estado.value == "error"}

    @app.post("/api/piezas", status_code=201)
    def subir_pieza(
        foto: UploadFile = File(...),
        credito_autor: str | None = Form(None),
        credito_url: str | None = Form(None),
        es_ejemplo: bool = Form(False),
    ):
        # Se prepara todo en una carpeta temporal y se mueve a datos/piezas/<id>/ dentro de
        # la transacción que crea la pieza: el trabajador nunca ve una pieza sin su foto.
        config.carpeta_piezas.mkdir(parents=True, exist_ok=True)
        tmp = config.carpeta_piezas / f".subida-{uuid.uuid4().hex}"
        tmp.mkdir()
        try:
            ext = Path(foto.filename or "").suffix.lower()
            original = tmp / f"original{ext if ext in EXTENSIONES_ORIGINAL else '.bin'}"
            with open(original, "wb") as f:
                shutil.copyfileobj(foto.file, f)
            revision = revisar_foto(original)
            if not revision.aceptada:
                return JSONResponse({"problemas": revision.problemas}, status_code=422)
            limpia = limpiar_foto(original, tmp / "borrador" / "foto.jpg")
            crear_portada(limpia, tmp / "borrador" / "portada.jpg")
            crear_miniaturas(limpia, tmp / "borrador")
            movida: list[Path] = []

            def preparar(i: int) -> None:
                destino = config.carpeta_piezas / str(i)
                if destino.exists():
                    # Carpeta sin fila (p. ej. la base se reseteó): se aparta, nunca se borra.
                    destino.rename(config.carpeta_piezas / f".huerfana-{i}-{uuid.uuid4().hex}")
                tmp.rename(destino)
                movida.append(destino)

            try:
                id_ = cola.crear_pieza(es_ejemplo=es_ejemplo, credito_autor=credito_autor,
                                       credito_url=credito_url, preparar=preparar)
            except BaseException:
                if movida:  # la fila no se confirmó: la carpeta vuelve a tmp y se borra abajo
                    movida[0].rename(tmp)
                raise
        finally:
            shutil.rmtree(tmp, ignore_errors=True)  # ya no existe si se movió
        return {"id": id_, "estado": cola.obtener(id_).estado.value}

    @app.get("/api/piezas")
    def listar_piezas():
        return [resumen(p) for p in cola.listar()]

    @app.get("/api/eventos")
    def eventos():
        """Server-Sent Events: el navegador recibe la lista de piezas cuando algo cambia."""
        def instantanea() -> list:
            return [resumen(p) for p in cola.listar()]

        return StreamingResponse(
            flujo_eventos(cola, instantanea, app.state.parar_eventos),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/piezas/{id_}/progreso")
    def progreso_pieza(id_: str):
        p = pieza(id_)
        if p is None:
            return _no_encontrada()
        pr = cola.progreso(p.id)
        return {"estado": pr.estado.value, "etapa": pr.etapa, "porcentaje": pr.porcentaje}

    @app.post("/api/piezas/{id_}/reintentar")
    def reintentar_pieza(id_: str):
        p = pieza(id_)
        if p is None:
            return _no_encontrada()
        try:
            nuevo = cola.aplicar(p.id, "reintentar")
        except TransicionInvalida as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)
        return {"id": p.id, "estado": nuevo.value}

    @app.post("/api/piezas/{id_}/reprocesar")
    def reprocesar_pieza(id_: str):
        p = pieza(id_)
        if p is None:
            return _no_encontrada()
        try:
            nuevo = cola.aplicar(p.id, "reprocesar")
        except TransicionInvalida as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)
        return {"id": p.id, "estado": nuevo.value}

    @app.put("/api/piezas/{id_}/ficha")
    def corregir_ficha(id_: str, datos: dict = Body(...)):
        p = pieza(id_)
        if p is None:
            return _no_encontrada()
        try:
            ficha = validar_ficha(datos)
        except FichaInvalida as exc:
            return JSONResponse({"errores": exc.errores}, status_code=422)
        try:
            nuevo = cola.editar_ficha(p.id, ficha)
        except TransicionInvalida as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)
        return {"id": p.id, "estado": nuevo.value, "ficha": ficha.a_dict()}

    @app.post("/api/piezas/{id_}/aprobar")
    def aprobar_pieza(id_: str):
        p = pieza(id_)
        if p is None:
            return _no_encontrada()
        try:
            cola.aprobar(p.id)
        except TransicionInvalida as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)
        return {"id": p.id, "estado": cola.obtener(p.id).estado.value}

    @app.get("/api/piezas/{id_}")
    def detalle_pieza(id_: str):
        p = pieza(id_)
        if p is None:
            return _no_encontrada()
        borrador = cola.carpeta_borrador(p.id)
        archivos = {n: f"/api/piezas/{p.id}/archivos/{n}" for n in ARCHIVOS_PERMITIDOS
                    if (borrador / n).is_file()}
        return {**asdict(p), **resumen(p), "archivos": archivos}

    @app.get("/api/piezas/{id_}/archivos/{nombre}")
    def archivo_pieza(id_: str, nombre: str):
        p = pieza(id_)
        if p is None or nombre not in ARCHIVOS_PERMITIDOS:
            return _no_encontrada()
        ruta = cola.carpeta_borrador(p.id) / nombre
        if not ruta.is_file():
            return _no_encontrada()
        return FileResponse(ruta, media_type=ARCHIVOS_PERMITIDOS[nombre])

    # check_dir=False: visor/ y node_modules pueden no existir todavía.
    raiz = config.raiz
    app.mount("/visor", StaticFiles(directory=raiz / "visor", check_dir=False), name="visor")
    app.mount("/vendor/three", StaticFiles(directory=raiz / "node_modules" / "three", check_dir=False))
    app.mount("/vendor/spark", StaticFiles(
        directory=raiz / "node_modules" / "@sparkjsdev" / "spark" / "dist", check_dir=False))
    app.mount("/", StaticFiles(directory=Path(__file__).parent / "estatico", html=True), name="panel")
    return app

