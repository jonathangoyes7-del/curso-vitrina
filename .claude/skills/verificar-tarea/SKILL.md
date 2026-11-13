---
name: verificar-tarea
description: Usar cuando se termina de construir una tarea del plan de Vitrina (docs/superpowers/plans/2026-11-13-vitrina.md) y toca cerrarla - comprobar el resultado, marcar sus casillas y commitear.
---

# Verificar tarea

Cierra una tarea del plan siempre igual: comprobar, mirar, marcar, commitear. Sin arrancar ningún servidor.

Argumento: el número de la tarea (p. ej. `5`). Si falta, se deduce de las casillas del plan que están a medias; si hay duda, se pregunta.

## Pasos

1. **Leer la tarea** en `docs/superpowers/plans/2026-11-13-vitrina.md`: sus pasos, su comprobación ("Resultado esperado") y el mensaje de commit exacto.

2. **Correr la comprobación** de la tarea traduciendo `py -m X` a `uv run python -m X`. Normalmente es `uv run pytest tests/test_<modulo>.py`; para ver el estado global, `uv run pytest` (excluye `gpu` y `ollama`). Solo se usa `-m gpu` o `-m ollama` si la tarea lo pide.
   - **Sin servidores:** no se ejecuta `iniciar.ps1`, `python -m panel`, `uvicorn`, `http.server` ni `npm run dev`/similares. Si una comprobación del plan exige servir algo (p. ej. abrir el visor por `http://127.0.0.1:8000`), no se hace: ese paso queda **sin comprobar** y se dice.
   - La cola y los tests respetan el orden de un trabajo a la vez; no se paraleliza nada.

3. **Mirar el resultado real** (salida completa de pytest, archivo generado). Se compara con el "Resultado esperado" del plan.
   - Si algo falla o no coincide: se para, se informa con la salida y **no se marca ni se commitea**.
   - Se cuenta lo que no se pudo comprobar (GPU, Ollama, servidor, pasos manuales de la persona, puntos de parada).

4. **Marcar las casillas** (`- [ ]` → `- [x]`) en el plan, solo las de pasos hechos y comprobados. No se marcan los pasos manuales ni los puntos de parada que la persona no ha dado por buenos. Se marca también la casilla del paso de commit, para que el cambio del plan entre en el mismo commit.

5. **Commit en `main`** (sin ramas nuevas):
   - `git status` y `git diff` primero; se añaden solo los archivos que la tarea pide más el plan, por nombre (nunca `git add -A`).
   - Jamás entran `datos/`, `fotos/`, `.env`, `sitio/` ni `.venv/`.
   - Mensaje: el exacto que da la tarea en el plan, en castellano, terminando con la línea `Co-Authored-By` de la atribución vigente.
   - Sin `--no-verify`. Si un hook falla, se arregla la causa.

6. **Informar** en castellano: qué se ejecutó, el resultado, qué casillas se marcaron, el hash del commit y lo que quedó sin comprobar.

## Errores comunes

| Error | Corrección |
|---|---|
| Marcar casillas porque el código "parece correcto" | Solo con salida real vista |
| Levantar el panel o `http.server` para comprobar | Prohibido; dejar el paso sin comprobar y decirlo |
| Cambiar el mensaje de commit | Usar el del plan tal cual |
| Commitear con `git add -A` | Añadir archivos por nombre |
