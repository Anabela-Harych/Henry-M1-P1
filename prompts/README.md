# Prompts versionados

Los prompts se mantienen en YAML fuera del código. `src/llm/prompt_loader.py` carga `version`, `system` y, cuando existen, ejemplos de entrada y salida. Se elige una versión por CLI con `--prompt`; por defecto se usa `v1_zero_shot.yaml`.

## Variantes

- `v1_zero_shot.yaml`: línea base con instrucciones directas y sin ejemplos.
- `v2-fewshot.yaml`: las reglas de la línea base más ejemplos sintéticos para las cuatro categorías.
- `v3-structured.yaml`: contexto dividido en rol y alcance, autoridad de la consulta, criterio de clasificación, respuesta y contrato de salida.

Cada archivo tiene una versión estable. Al cambiar reglas o ejemplos, creá una nueva versión en vez de reescribir el archivo usado en una corrida; así los resultados pueden vincularse con el prompt exacto.

## Experimentos

Ejecutá `python -m evals.runner --execute` para comparar prompts y proveedores sobre el mismo dataset. Registrá métricas y selección por modelo en [`EXPERIMENTS.md`](EXPERIMENTS.md). El reporte detallado y la hoja de revisión se generan en `data/reports/`; usá esta última para evaluar manualmente pertinencia, seguridad, acciones y concisión.
