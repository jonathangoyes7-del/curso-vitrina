# Calidad de Idol

## Qué hace cada ajuste

- **Pasos (`steps`, 25 por defecto):** Idol parte de ruido y lo limpia paso a paso hasta formar la pieza. Más pasos, más fino, pero el tiempo crece en proporción. No cambia el peso del archivo.
- **Gaussianas (`num_gaussians`, 262 144):** el splat es una nube de manchitas translúcidas. Más manchitas, más detalle y más peso (casi en proporción). Rango válido: 32 768 a 1 048 576, múltiplo de 32.
- **Semilla (`seed`, 42):** fija el ruido inicial. Misma foto y misma semilla dan la misma pieza; otra semilla da una variante (útil para reintentar).
- **Modo (`mode="real"`):** `real` es para fotos de verdad y recorta con más margen (1,7); `synthetic` es para renders (1,2).
- **`cfg_strength` (3,0):** cuánto obedece el modelo a la foto frente a inventar.

<!-- tablas:inicio -->
Foto: `vaso_ceramica.jpg`, `mode="real"`, `seed=42`, `cfg_strength=3.0`, medido con `optimize=True` tras un calentamiento.

### Gaussianos (pasos = 50)

| Gaussianos | Segundos | Pico de VRAM (GB) | PLY (MB) | Gaussianos en el PLY |
|---:|---:|---:|---:|---:|
| 131 072 | 66.0 | 4.98 | 8.5 | 131 072 |
| 262 144 | 66.6 | 4.98 | 17.0 | 262 144 |
| 524 288 | 67.5 | 4.98 | 34.0 | 524 288 |

### Pasos (gaussianos = 262 144)

| Pasos | Segundos | Pico de VRAM (GB) | PLY (MB) | Gaussianos en el PLY |
|---:|---:|---:|---:|---:|
| 25 | 34.1 | 4.98 | 17.0 | 262 144 |
| 50 | 66.6 | 4.98 | 17.0 | 262 144 |
<!-- tablas:fin -->

## Lectura

- Las gaussianas **no cambian el tiempo** (66-68 s) ni la VRAM (4,98 GB); solo el peso del PLY (8,5 / 17,0 / 34,0 MB).
- Los pasos **sí cambian el tiempo**: 25 pasos tardan 34,1 s frente a 66,6 s con 50 (51 %, casi la mitad). El PLY pesa lo mismo (17,0 MB) y la VRAM es igual.
- Ojo: lo medido es tiempo y peso. **No se ha comparado la calidad visual** de 25 contra 50 pasos ni de los tres recuentos en `ver_splat.html` (no se hizo captura); eso queda para que lo mire la persona con los PLY de `datos/calidad/`.

## Decisión

- **Pasos: 25** (era 50). Tras ver los dos vasos de la misma foto en `ver_splat.html` (`datos/calidad/g262144_s25.ply` y `g262144_s50.ply`), la persona eligió 25: tarda 34,1 s en vez de 66,6 s, con el mismo peso (17,0 MB) y la misma VRAM. `ParametrosIdol.steps` vale ahora 25 y el test `test_parametros_por_defecto` lo refleja.
- **Gaussianas: 262 144** (sin cambios). El SPZ de la Tarea 6 baja el recuento solo si no cabe en 10 MB.
- Las tablas de arriba se midieron con 50 pasos como referencia; `scripts/calidad_idol.py` fija sus propios valores, así que no depende del valor por defecto.
