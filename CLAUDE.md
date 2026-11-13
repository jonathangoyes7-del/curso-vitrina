# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado actual

El repo solo contiene documentación (`README.md`, `.gitignore`, `docs/superpowers/`). **Todavía no hay código, ni `pyproject.toml`, ni tests.** La fuente de verdad es:

- Diseño: `docs/superpowers/specs/2026-11-13-vitrina-design.md`
- Plan (14+ tareas, con interfaces, tests y mensajes de commit exactos): `docs/superpowers/plans/2026-11-13-vitrina.md`

Léelos antes de construir nada. El plan se ejecuta tarea por tarea (superpowers:subagent-driven-development o executing-plans) y las tareas posteriores consumen las interfaces que producen las anteriores. Las respuestas y los commits van en castellano ("Agrega …").

## Qué es

Vitrina: catálogo 3D público de una tienda de artesanía. Un panel local en Python convierte una foto en splat 3D + ficha (IA local) + QR + Reel, y publica un sitio estático en GitHub Pages (`https://jonathangoyes7-del.github.io/curso-vitrina/`). No hay carrito, pagos, cuentas ni servidor en línea.

## Comandos (previstos en el plan; aún no existen)

Windows 11, PowerShell. El plan abrevia `py` = `.\.venv\Scripts\python.exe`.

- Instalar: `.\instalar.ps1` (venv, PyTorch cu128, Idol, spz, Playwright Chromium, `npm ci`). Lanzar el panel: `.\iniciar.ps1` o `py -m panel` (`127.0.0.1:8765`).
- Tests: `py -m pytest` (por defecto `-m 'not gpu and not ollama'`; los de `navegador` sí corren). Uno solo: `py -m pytest tests/test_cola.py::test_recuperar_interrumpidos`. Con GPU: `py -m pytest -m gpu`. Con Ollama: `py -m pytest -m ollama`.
- Lote de Idol: `py -m panel.lote ENTRADA SALIDA [--num-gaussianos N]`.

## Arquitectura

Un solo proceso local (FastAPI + Uvicorn) con cola SQLite (`datos/vitrina.sqlite`) y un hilo trabajador que ejecuta **un trabajo a la vez** (Idol y Gemma no pueden compartir la VRAM): Idol (foto → PLY) → SPZ (≤ 10 MB, baja gaussianos 262 144→131 072→65 536 si no cabe) → Gemma (`gemma4:12b` vía Ollama, ficha JSON) → QR → Reel (Playwright graba el visor a 1080×1920, ffmpeg → MP4).

- `panel/`: app local (`cola.py` con la máquina de estados, `api.py`, `ficha.py`, `fotos.py`, `splat.py`, `idol.py`/`lote.py`…). `panel/catalogo/`: generador del sitio con Jinja2 (`generador.py`, `publicar.py`).
- `visor/visor.js`: **un único visor** Three.js 0.186.0 + Spark 2.4.0 compartido por la página de pieza, la de incrustación, el panel y el Reel (modos `pagina`, `embed`, `reel`).
- `datos/` (fotos originales, splats, Reels, cola) y `sitio/` (generado) están fuera de `main`. `sitio/` se publica entero en la rama huérfana `gh-pages` de un solo commit con `git push --force`; no hay Actions.
- Máquina de estados: `pendiente → procesando → para revisar → aprobada → publicada`, más `despublicada` y `error`. Solo entra al sitio lo `aprobada`/`publicada`. Una pieza publicada que se edita pasa a `para revisar` pero el sitio sigue mostrando la versión aprobada (`vigente/`) hasta que se apruebe el borrador (`borrador/`). La tabla exacta de transiciones está en la Tarea 8 del plan.
- Estado de la pieza vs. archivos: `datos/piezas/<id>/borrador|vigente`. `aprobar` copia `borrador/` a `vigente/` (sin el PLY).

## Restricciones que no se deben romper

- El panel escucha solo en `127.0.0.1`; `TrustedHostMiddleware` + cabecera `X-Vitrina: panel` obligatoria en todo método no seguro (anti-CSRF y anti DNS rebinding).
- Nada se publica sin revisión humana. Nunca llegan al repo público fotos originales con EXIF (se usa una copia limpia con `exif_transpose` aplicado primero), la cola ni `datos/`.
- El `slug` no cambia una vez aprobada la pieza (rompería QR impresos e `<iframe>` ajenos).
- Gemma: categoría solo de `Cerámica`, `Madera tallada`, `Tejidos de lana`; JSON roto o categoría inválida → un reintento y luego estado `error`.
- Rutas del sitio relativas (subruta de GitHub Pages); solo son absolutas `og:image`, `og:url` y el `src` del `<iframe>` copiable.
- Presupuesto de peso: splat ≤ 10 MB; página de pieza < 500 KB con gzip contando solo lo propio de la página (Three y Spark son compartidos, tope aparte de 1,6 MB gzip). La galería no carga el visor.
- Textos obligatorios: `Built with DINOv3` en el pie (enlace a la licencia de DINOv3), etiqueta `Ejemplo` y crédito `Foto: <autor> en Unsplash` en las piezas de ejemplo.
- Idol necesita PyTorch cu128 (GPU Blackwell, `sm_120`) y usa el VAE de `black-forest-labs/FLUX.2-klein-4B` (Apache 2.0) en vez del de FLUX.2-dev (no comercial). La Tarea 2 (pico de validación) es un **punto de parada**: si falla, se detiene el trabajo y se consulta; no hay modelo alternativo.
- Versiones fijadas sin `^` (`package.json`) y con `==` (`pyproject.toml`). Paleta como tokens CSS: `--papel #F5F1E8`, `--grafito #2E2D2B`, `--cobalto #2347A8`; interfaz en castellano (`lang="es"`).

## Reglas fijas

- **Stack cerrado:** Python gestionado con **uv**, Idol sobre la GPU local, Ollama con Gemma para la ficha, Three.js + Spark en el visor y un sitio estático en GitHub Pages. No se cambia ni se añade una alternativa sin consultar. El plan está escrito con `.venv` y `pip`; al ejecutarlo se usa uv (`uv sync`, `uv add`, `uv run pytest`) y se avisa de cada diferencia.
- **Licencias:** solo pesos y modelos cuya licencia permita el uso comercial. Jamás el modelo de imagen no comercial (el VAE de `FLUX.2-dev`); se usa el de `FLUX.2-klein-4B`. Ante la duda sobre una licencia, se para y se pregunta.
- **Idol y la ficha nunca corren a la vez:** la cola los pone en fila, un trabajo a la vez. No se paraleliza ni se salta la cola, ni siquiera en scripts o tests.
- **No se tocan** las carpetas `datos/` y `fotos/` ni el archivo `.env` (no se leen, editan, mueven ni borran, ni se commitean). Si una tarea del plan necesita escribir en `datos/` (por ejemplo `datos/pico/` en la Tarea 2), se pide a la persona que lo haga o se le consulta antes.
- **Cerrar cada tarea comprobando el resultado:** se ejecuta lo que se construyó y se mira la salida real (tests, captura del visor, archivo generado). No se da por bueno algo solo porque el código parece correcto. Si no se pudo comprobar, se dice.
- **Alcance y rama:** se commitea en `main`, sin ramas nuevas, y cada commit toca solo lo que la tarea pide.
