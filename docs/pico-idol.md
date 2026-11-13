# Pico de validación de Idol (Tarea 2)

Resultado: **funciona** en la RTX 5060 Ti (Blackwell, `sm_120`) con el VAE de `FLUX.2-klein-4B` (Apache 2.0).

## Versiones

| Elemento | Valor |
|---|---|
| `idol-sdk` (paquete `idol`) | commit `8db700349a5570aac390e4780fa32e3eed6b587a` (HEAD de `main`, 2026-11-13) |
| torch / CUDA | `2.11.0+cu128` / `12.8` |
| GPU | NVIDIA GeForce RTX 5060 Ti, 16 GB |
| VAE | `black-forest-labs/FLUX.2-klein-4B` (no se descargó nunca `FLUX.2-dev`) |
| Pesos | `speridlabs/idol`, `facebook/dinov3-vith16plus-pretrain-lvd1689m` |

## Medidas (foto: `fotos/vaso_ceramica.jpg`, `mode="real"`, `seed=42`, 262 144 gaussianos)

- Carga del pipeline: 8,0 s (pesos ya en caché).
- Tiempo por pieza: **132,3 s** con `optimize=False` (primer pico). **Modo rápido** (`optimize=True` con `triton-windows`): **103,1 s** la primera vez (incluye compilar) y **81,6 s** con la caché de compilación caliente. Carga del pipeline 7,6 s; pico de VRAM idéntico (4,98 GB).
- Pico de VRAM (`torch.cuda.max_memory_allocated()`): **4,98 GB** (< 16 GB). Al empezar ya había ~4 GB ocupados por otros procesos del PC.
- `pieza.ply`: 17,8 MB (el SPZ de la Tarea 6 lo bajará a ≤ 10 MB).

## Desviaciones respecto al plan

- El paquete se llama `idol`, no `idol-sdk`: se añadió con `uv add "idol @ git+https://github.com/speridlabs/idol-sdk@<sha>"` (queda en `pyproject.toml` y `uv.lock`).
- **Sin Triton, `torch.compile` falla** (`TritonMissing`). Se añadió `triton-windows==3.9.0.post30` (fork para Windows de Triton, licencia MIT) y el script usa `optimize=True` (modo rápido). No hace falta Visual Studio. `ATTN_BACKEND=sdpa` no hizo falta. Alternativa sin la dependencia: `optimize=False` (132 s).
- En Git Bash `getpass.getuser()` falla si falta `USERNAME` (al importar torch._inductor). En PowerShell no pasa; en Git Bash usar `USERNAME=...`.

## Constantes para el visor (Tarea 11)

Spark 2.4.0, `SplatMesh({ url })` con el PLY tal cual sale de Idol:

- **Rotación del splat**: el PLY sale boca abajo; hace falta `splat.quaternion.set(1, 0, 0, 0)` (x, y, z, w; giro de 180° sobre X, convención OpenCV). Con la identidad la base de arcilla quedaba arriba.
- **Caja del splat** (`getBoundingBox`): `(-0.32, -0.50, -0.33)` → `(0.31, 0.50, 0.33)`: centrada en el origen, altura 1,0.
- **Encuadre**: objetivo de cámara `(0, 0, 0)`, cámara en `(0, 0, 2.5)`, `PerspectiveCamera(fov 50)`. La pieza entera cabe con margen; vistas desde `(1.8, 0.3, 0.9)` y `(-1.5, 0.2, -1.5)` también se ven bien (la pieza es realmente 3D).

## Cómo se comprobó

Visor `herramientas/ver_splat.html` servido con `uv run python -m http.server 8000` y capturas con Chrome (Playwright, fuera del repo). Capturas en `datos/pico/cap/` (no se commitea): `a.png` (identidad, boca abajo), `b.png` (`q=1,0,0,0`, frontal), `c.png` y `d.png` (otros ángulos).

Parámetros de URL de la herramienta: `?splat=RUTA&q=x,y,z,w&cam=x,y,z&target=x,y,z`.
