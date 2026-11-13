# Vitrina: diseño

Fecha: 2026-11-13

## Intención

Vitrina es el catálogo 3D público de una tienda pequeña de artesanía (cerámica, madera tallada y tejidos de lana). Sirve para **mirar las piezas y compartirlas**, no para vender en línea. Toda la IA corre en el PC de la dueña o dueño de la tienda. Lo publicado es un sitio estático gratuito en GitHub Pages.

## Objetivos

- Cada pieza publicada tiene:
  - un **visor 3D** que gira con el ratón y con el dedo;
  - un **componente para incrustarla** en cualquier web (un `<iframe>`);
  - su **código QR**, que apunta a la página de la pieza;
  - un **Reel vertical** para redes sociales.
- La persona artesana trabaja en un **panel local**: sube una foto, ve la cola de trabajos, revisa la ficha y publica.
- La **ficha** la redacta una IA local en castellano y siempre la revisa una persona antes de publicarse. Tiene cuatro campos: nombre, materiales, categoría y cuidados.

## No objetivos

Carrito, pagos, cuentas de usuario, precios, datos de contacto, dominio propio, servidor en línea y varios usuarios en el panel.

## Antiobjetivos (sería un fracaso aunque funcione)

- Que algo se publique sin que la persona lo haya revisado.
- Que lleguen al repo público datos privados: fotos originales con metadatos EXIF (por ejemplo, la ubicación GPS del móvil), la cola o archivos de trabajo.
- Que las páginas de pieza pesen tanto que no carguen bien en un móvil.
- Que el panel se pueda abrir desde otro equipo de la red.

## Restricciones

- **Equipo:** Windows 11, Ryzen 5 9600X y NVIDIA RTX 5060 Ti con 16 GB (arquitectura Blackwell, necesita PyTorch con CUDA 12.8 o superior). Ya están instalados Python 3.11, Node, Ollama, ffmpeg y git.
- **3D:** [Speridlabs Idol](https://huggingface.co/speridlabs/idol) (Apache 2.0, SDK `speridlabs/idol-sdk`). Recibe una imagen y devuelve un **splat gaussiano**, no una malla. Usa unos 7 GB de VRAM. Depende de DINOv3. La [licencia de DINOv3](https://ai.meta.com/resources/models-and-libraries/dinov3-license) permite el uso comercial y **exige** mostrar "Built with DINOv3" de forma visible. Además, quien redistribuya materiales de DINO tiene que incluir una copia de la licencia. Como el sitio no redistribuye pesos ni código de DINOv3, basta con el aviso.
- **Primera fase del plan:** un pico de validación que instale Idol con PyTorch cu128 en esta GPU y genere un splat que Spark muestre. Si falla, el trabajo se detiene y se vuelve a hablar con la persona antes de seguir. No hay un modelo alternativo aprobado.
- **Ficha:** `gemma4:12b` en Ollama, que ya está instalado y acepta imágenes.
- **Entrada:** una foto nítida por pieza, con la pieza entera. Las piezas son casi todas mate y no hay vidrio.
- **Publicación:** se publica desde este mismo repo (`jonathangoyes7-del/curso-vitrina`), que es público, con la URL gratuita `https://jonathangoyes7-del.github.io/curso-vitrina/`. Como el sitio vive en una subruta, todas las rutas tienen que ser relativas. GitHub Pages admite archivos de hasta 100 MB y sitios de hasta 1 GB.
- **Visor:** Three.js con Spark (renderizador de splats para Three).
- **Identidad:** paleta propia de papel, grafito y cobalto. En el pie del catálogo va el aviso **"Built with DINOv3"** como crédito. Las fotos de ejemplo son de Unsplash, cada una con su crédito.

## Enfoques considerados

- **A. Todo en Python con un sitio HTML simple (el elegido).** Un panel local en Python, un único proceso que ejecuta la cola y un generador de sitio con plantillas. Se eligió porque Idol ya es Python, así que queda un solo lenguaje y una sola instalación. Además, el Reel se graba con el mismo visor que la web.
- **B. Panel en Python y sitio con Astro.** Se descartó porque obliga a mantener dos herramientas y una galería con fichas no las necesita.
- **C. Reel renderizado en Python, sin navegador.** Se descartó porque requiere compilar librerías de render para Blackwell y el Reel no se vería igual que el visor de la web.

## Lo decidido

### Estructura del repo

- `panel/`: la app local en Python. Escucha solo en `127.0.0.1`.
- `datos/`: fotos originales, splats sin comprimir, Reels y la cola en SQLite. Ya está en `.gitignore` y nunca se publica.
- `sitio/`: el sitio estático generado. Está en `.gitignore` y **no** se commitea en `main`.
- **Rama `gh-pages`, huérfana y de un solo commit.** Cada publicación la reemplaza entera con el contenido de `sitio/` y hace `git push --force`. GitHub Pages se configura como "Deploy from a branch" con `gh-pages` en la raíz. Así lo que se despublica desaparece de verdad del repo (salvo copias que alguien ya haya clonado), el repo no crece con cada splat y `docs/` no se publica. No hace falta ninguna Action.

### Flujo de una pieza

1. **Subir.** Se sube la foto en el panel. Se guarda el original en `datos/` y se crea una copia **sin metadatos EXIF**, que es la única que se usa después.
2. **Cola.** Se procesa **un trabajo a la vez**, para que Idol y Gemma no compitan por la VRAM. Los estados son: `pendiente → procesando → para revisar → aprobada → publicada`, más `despublicada` y `error`, con un botón para reintentar. El panel muestra la cola y en qué etapa está cada pieza. **Solo entra al sitio lo que está `aprobada` o `publicada`.** Si una pieza publicada se edita o se reprocesa, el cambio queda como borrador `para revisar`. Mientras tanto, el sitio sigue mostrando la última versión aprobada, que se guarda en `datos/`. Cuando se aprueba el borrador, reemplaza a esa versión.
3. **3D.** Idol genera el splat. Se guarda con unos 250 000 gaussianos en un formato comprimido que Spark lea, para que cada pieza pese pocos MB.
4. **Ficha.** Gemma recibe la foto y devuelve un borrador en castellano con nombre, materiales, categoría y cuidados. La categoría sale de una lista fija: Cerámica, Madera tallada y Tejidos de lana.
5. **QR.** Se genera el QR con la URL pública de la pieza.
6. **Reel.** Un navegador sin ventana (Playwright con Chromium) abre el visor en modo Reel a 1080×1920 y graba la pieza mientras da una vuelta completa. ffmpeg lo convierte en MP4 H.264.
7. **Revisar.** En el panel se ve el visor, se edita la ficha, se ven el QR y el Reel, y se aprueba la pieza.
8. **Publicar.** El botón regenera `sitio/` completo con las piezas aprobadas y publicadas, y reemplaza la rama `gh-pages` con ese contenido. Usa las credenciales de git que ya están configuradas en el PC.

### Peso en el móvil

- Cada splat comprimido debe pesar **10 MB o menos**, y la página de pieza sin el splat, menos de 500 KB. La referencia es un móvil de gama media con 4G.
- La galería muestra **solo imágenes**. El visor 3D se carga al abrir una pieza.
- Si un móvil renderiza el splat con dificultad, se baja la cantidad de gaussianos antes de reducir la calidad de otras partes.

### Instalación y uso

Quien usa el panel es la misma persona que lo instala, desde este PC. Basta con un script de instalación (entorno de Python, PyTorch cu128, Idol, Playwright con Chromium y la comprobación de que `gemma4:12b` está en Ollama) y un lanzador del panel, documentados en el README.

### Piezas de ejemplo

Son tres piezas hechas a partir de fotos de Unsplash, una por categoría: Cerámica, Madera tallada y Tejidos de lana. Sirven para probar el flujo completo y ver el sitio antes de que haya fotos propias. En la galería y en su página llevan la etiqueta visible **"Ejemplo"**, y en su página muestran el crédito de Unsplash con el autor y el enlace. La persona las borra desde el panel cuando publica sus propias piezas. Quien lo construya elige fotos de Unsplash de piezas mate, sin vidrio y fotografiadas enteras.

### Sitio público

- **Galería:** una cuadrícula de piezas con una imagen de portada de cada una y un filtro por categoría.
- **Página de pieza:** visor 3D (ratón y táctil), ficha, QR, botón Compartir (usa la Web Share API y, si el navegador no la tiene, ofrece copiar el enlace) y el código `<iframe>` listo para copiar. Incluye etiquetas Open Graph con la portada, para que el enlace se vea bien al compartirlo.
- **Página de incrustación** (`embed/<slug>/`): solo el visor, sin el resto de la página. Es la que carga el `<iframe>`.
- **Pie:** "Built with DINOv3" y, en las piezas de ejemplo, el crédito de Unsplash con autor y enlace.
- Interfaz en castellano, con la paleta papel, grafito y cobalto.

## Decisiones mías para revisar

- Unos 250 000 gaussianos por pieza en formato comprimido, en lugar del millón que permite Idol.
- El sitio se publica en una rama `gh-pages` huérfana que se reemplaza en cada publicación, para que despublicar sea real.
- El presupuesto de peso: 10 MB o menos por splat y la galería solo con imágenes.
- Si una pieza publicada se edita, la versión anterior sigue en el sitio hasta que se apruebe la nueva.
- El Reel se descarga desde el panel y **no** se sube al sitio, para que el repo no crezca con videos.
- Las fotos se publican sin EXIF.
- La categoría sale de una lista fija de tres.
- Las piezas publicadas se pueden editar o despublicar desde el panel. El cambio aparece en la siguiente publicación.
- El panel tiene un campo opcional "crédito de la foto" (autor y enlace) para las fotos de Unsplash.

## Lo que queda a criterio de quien lo construya

- El framework web del panel (por ejemplo FastAPI o Flask) y cómo se actualiza la cola en pantalla.
- Quitar el fondo de la foto antes de pasarla a Idol, si Idol no lo hace por su cuenta.
- El formato de splat comprimido, siempre que Spark lo lea.
- Si Three y Spark se copian en `sitio/vendor/` o se cargan desde un CDN con la versión fijada.
- El texto exacto que se le pide a Gemma, la duración del Reel (unos 10 a 15 segundos) y los detalles visuales dentro de la paleta.
- Cómo se forma el `slug` de cada pieza a partir de su nombre.
