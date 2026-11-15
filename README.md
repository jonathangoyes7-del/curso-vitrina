# Vitrina

Catálogo 3D para una tienda pequeña de artesanía, hecho con IA que corre en tu propio equipo.
Subes una foto de una pieza y Vitrina crea su modelo 3D, la ficha (nombre, materiales, categoría, cuidados), un código QR y un vídeo corto. Tú lo revisas y, cuando lo apruebas, se publica en un sitio web gratuito.

Sitio público: <https://jonathangoyes7-del.github.io/curso-vitrina/>

No hay carrito, pagos ni cuentas: es para **mirar y compartir** las piezas.

## Qué necesitas

- Windows 11 con una tarjeta gráfica NVIDIA (probado con una RTX 5060 Ti de 16 GB).
- Instalados de antemano: [uv](https://docs.astral.sh/uv/), [Node.js](https://nodejs.org/), ffmpeg (`winget install Gyan.FFmpeg`), [git](https://git-scm.com/) y [Ollama](https://ollama.com/download).
- Una cuenta gratuita de [Hugging Face](https://huggingface.co/).
- Git con tus credenciales de GitHub ya configuradas en este equipo (es lo que usa el botón de publicar).

## Instalación (una sola vez)

1. **Acceso a DINOv3.** Con tu cuenta de Hugging Face, entra en <https://huggingface.co/facebook/dinov3-vith16plus-pretrain-lvd1689m> y acepta los términos. Sin esto, la creación del 3D falla.
2. **Ollama:** descarga el modelo de las fichas: `ollama pull gemma4:12b`.
3. En PowerShell, dentro de esta carpeta: `.\instalar.ps1`.
   - Comprueba los programas, crea el entorno de Python 3.11 con PyTorch para CUDA 12.8, instala Idol, el visor 3D y el navegador de pruebas, y te pide el token de Hugging Face si aún no has abierto sesión (se crea en <https://huggingface.co/settings/tokens>).
   - Termina comprobando que PyTorch ve la tarjeta gráfica.
   - Se puede repetir sin miedo: no borra el entorno que ya existe.

## Uso diario

**Doble clic en `iniciar.bat`.** Se abre una ventana negra (déjala abierta mientras trabajas) y, en unos segundos, el panel en el navegador, en <http://127.0.0.1:8765/>. Si ya estaba abierto, solo vuelve a mostrarlo. Para cerrar Vitrina, cierra esa ventana negra.

Al arrancar, el panel comprueba que **Ollama** y la **tarjeta gráfica** están listos. Si Ollama está apagado, te lo dice arriba, en rojo: ábrelo (icono de la llama junto al reloj) y pulsa «Volver a comprobar».

El panel solo es accesible desde este equipo; no se puede abrir desde otro dispositivo de la red.

### El flujo: subir → revisar → aprobar → publicar

1. **Subir.** Arrastra una o varias fotos al recuadro (o elígelas con el botón). Para que salgan bien, mira [docs/guia-fotografia.md](docs/guia-fotografia.md). Cada foto entra en una cola y se procesa **de una en una** (cada pieza tarda un rato; la barra de su tarjeta muestra el avance).
2. **Revisar.** Cuando una pieza pasa a «para revisar», púlsala: verás la foto, el 3D (botón «Ver en 3D»), el QR y la ficha. Corrige lo que haga falta.
3. **Aprobar.** «Aprobar» guarda lo que ves y deja la pieza lista para el sitio. Nada se publica sin que lo apruebes.
4. **Publicar.** «Publicar catálogo» te pregunta, en la misma página, cuántas piezas se van a publicar; confirma con «Sí, publicar». Esto **reemplaza** el sitio público por el catálogo actual. GitHub tarda un par de minutos en mostrarlo.

Si editas una pieza ya publicada, el sitio sigue mostrando la versión aprobada hasta que apruebes la nueva.

El tono de las fichas (cómo habla tu tienda) está en [`tono_fichas.md`](tono_fichas.md): edítalo con tranquilidad, se lee de nuevo en cada ficha.

### Piezas de ejemplo

Para probar todo antes de tener tus fotos hay tres piezas de ejemplo (fotos de Unsplash, una por categoría). Se crean con `uv run python -m panel.ejemplos`, pasan por la cola como cualquier foto y llevan la etiqueta «Ejemplo» y el crédito del autor.

**Cómo quitarlas:** el panel todavía no tiene botón de borrar. La lógica existe en `panel/cola.py` (`Cola.borrar` y `Cola.despublicar`), pero falta conectarla a la API y a la pantalla.

## Configurar GitHub Pages (una sola vez)

Cada publicación sube el sitio a la rama `gh-pages` del repositorio (con un solo commit, sustituido cada vez). En GitHub: **Settings → Pages → Build and deployment → Source: «Deploy from a branch»**, rama `gh-pages`, carpeta `/ (root)`. No hace falta ninguna Action.

## Desarrollo

```
uv run pytest                 # tests (sin GPU ni Ollama)
uv run pytest -m gpu          # con la GPU
uv run pytest -m ollama       # con Ollama encendido
uv run python -m panel        # lo mismo que iniciar.bat
```

El diseño y el plan están en `docs/superpowers/`.

## Créditos y licencias

La lista completa, con licencias, está en la página «Créditos» del sitio.

- **Idol** (Speridlabs, Apache 2.0) crea el 3D a partir de una foto. **Built with DINOv3**: usa DINOv3 de Meta bajo su [licencia](https://ai.meta.com/resources/models-and-libraries/dinov3-license).
- **Gemma 4** (Google, Apache 2.0), ejecutado en local con Ollama, redacta las fichas.
- **Three.js** (MIT) y **Spark** (World Labs, MIT) muestran las piezas en 3D en el navegador.
- Fotos de las piezas de ejemplo: **[Unsplash](https://unsplash.com/)**, con el crédito de cada autor en su pieza.
