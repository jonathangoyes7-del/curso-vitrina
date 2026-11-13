"""API local del panel (Tarea 9, parte que no depende de la cola ni de la ficha)."""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from panel.config import Config
from panel.fotos import crear_portada, limpiar_foto, revisar_foto

ARCHIVOS_PERMITIDOS = {
    "foto.jpg": "image/jpeg",
    "portada.jpg": "image/jpeg",
    "entrada.png": "image/png",
    "pieza.spz": "application/octet-stream",
    "qr.svg": "image/svg+xml",
    "reel.mp4": "video/mp4",
}
EXTENSIONES_ORIGINAL = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}
ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")


def _no_encontrada() -> JSONResponse:
    return JSONResponse({"detail": "No encontrada"}, status_code=404)


def crear_app(config: Config) -> FastAPI:
    # Provisional: sin Cola (Tarea 8) la pieza vive solo como carpeta en datos/piezas/<id>/.
    # Cuando exista la Cola, el estado y los metadatos salen de ella.
    app = FastAPI(title="Vitrina: panel local")
    app.state.config = config
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def exigir_cabecera(request, call_next):
        if request.method not in METODOS_SEGUROS and request.headers.get("x-vitrina") != "panel":
            return JSONResponse({"detail": "Falta la cabecera X-Vitrina: panel"}, status_code=403)
        return await call_next(request)

    def carpeta(id_: str) -> Path | None:
        if not ID_VALIDO.match(id_):
            return None
        c = config.carpeta_piezas / id_
        return c if c.is_dir() else None

    def resumen(c: Path) -> dict:
        meta = _leer_meta(c)
        return {"id": c.name, "slug": None, "estado": "pendiente", "nombre": None,
                "error": None, "es_ejemplo": bool(meta.get("es_ejemplo", False))}

    @app.post("/api/piezas", status_code=201)
    def subir_pieza(
        foto: UploadFile = File(...),
        credito_autor: str | None = Form(None),
        credito_url: str | None = Form(None),
        es_ejemplo: bool = Form(False),
        # Solo para que «Try it out» de /docs envíe la cabecera; la exige el middleware.
        x_vitrina: str = Header("panel", alias="X-Vitrina"),
    ):
        id_ = uuid.uuid4().hex
        c = config.carpeta_piezas / id_
        c.mkdir(parents=True)
        try:
            ext = Path(foto.filename or "").suffix.lower()
            original = c / f"original{ext if ext in EXTENSIONES_ORIGINAL else '.bin'}"
            with open(original, "wb") as f:
                shutil.copyfileobj(foto.file, f)
            revision = revisar_foto(original)
            if not revision.aceptada:
                shutil.rmtree(c)
                return JSONResponse({"problemas": revision.problemas}, status_code=422)
            limpia = limpiar_foto(original, c / "borrador" / "foto.jpg")
            crear_portada(limpia, c / "borrador" / "portada.jpg")
            (c / "meta.json").write_text(json.dumps(
                {"credito_autor": credito_autor, "credito_url": credito_url,
                 "es_ejemplo": es_ejemplo}, ensure_ascii=False), encoding="utf-8")
        except BaseException:
            shutil.rmtree(c, ignore_errors=True)
            raise
        return {"id": id_, "estado": "pendiente"}

    @app.get("/api/piezas")
    def listar_piezas():
        if not config.carpeta_piezas.is_dir():
            return []
        carpetas = sorted((c for c in config.carpeta_piezas.iterdir() if c.is_dir()),
                          key=lambda c: c.stat().st_mtime)
        return [resumen(c) for c in carpetas]

    @app.get("/api/piezas/{id_}")
    def detalle_pieza(id_: str):
        c = carpeta(id_)
        if c is None:
            return _no_encontrada()
        archivos = {n: f"/api/piezas/{id_}/archivos/{n}" for n in ARCHIVOS_PERMITIDOS
                    if (c / "borrador" / n).is_file()}
        return {**resumen(c), **_leer_meta(c), "archivos": archivos}

    @app.get("/api/piezas/{id_}/archivos/{nombre}")
    def archivo_pieza(id_: str, nombre: str):
        c = carpeta(id_)
        if c is None or nombre not in ARCHIVOS_PERMITIDOS:
            return _no_encontrada()
        ruta = c / "borrador" / nombre
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


def _leer_meta(c: Path) -> dict:
    try:
        return json.loads((c / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
