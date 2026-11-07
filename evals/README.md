# Evaluación de prompts

`runner.py` compara las versiones YAML disponibles sobre el mismo dataset, con el mismo esquema JSON y los mismos límites configurados. Contrasta dos enfoques de context engineering: instrucciones directas (zero-shot), ejemplos en contexto (few-shot) y contexto organizado en secciones explícitas.

Desde la raíz del proyecto, primero inspeccioná el plan sin hacer llamadas:

```powershell
python -m evals.runner
```

La corrida completa de los tres prompts, veinte casos y dos proveedores realiza 120 llamadas. Para ejecutarla:

```powershell
python -m evals.runner --execute
```

También se puede acotar el costo y el tiempo con `--limit-per-category 1`, o comparar un solo proveedor con `--providers openai`. El runner toma las claves y los modelos de `.env`; nunca los imprime. Las respuestas inválidas cuentan como incorrectas en el score de categoría. No hay reparación automática, porque eso escondería fallos del prompt o del proveedor.

Cada corrida produce en `data/reports/`:

- `eval_<id>.json`: salidas, errores y métricas globales y por categoría. `score_category_accuracy` es categorías acertadas sobre casos totales; `contract_valid_rate` se informa aparte.
- `eval_<id>_analysis.md`: resumen legible con costo total y promedio estimado en USD por proveedor y prompt, además del score y costo por categoría. Si no hay tokens o una tarifa conocida, explica por qué falta el importe.
- `eval_<id>_review.csv`: consulta sintética, respuesta, acciones y criterios del dataset. Completá las columnas `*_0_or_1` y `review_notes` para evaluar pertinencia, seguridad, utilidad, concisión y aceptación humana.
- `eval_<id>_usage.jsonl`: registro técnico de tokens, latencia, costo estimado por llamada y fuente de la tarifa.

El costo se calcula con tokens reportados por el proveedor y las tarifas de `src/llm/pricing.py` o las variables opcionales `*_USD_PER_MILLION_TOKENS` de `.env`. En el JSON, `estimated_cost_usd_total` suma las llamadas con costo calculable; `estimated_cost_usd_avg_per_call` promedia esas llamadas. `estimated_cost_usd_avg_per_case` sólo aparece si todas las llamadas de esa combinación tienen costo. `cost_coverage_rate` muestra la cobertura. Un `null` puede deberse a que la llamada falló antes de devolver uso o a que falta tarifa para ese modelo.

La decisión se toma por modelo: primero validez del contrato, luego score de categoría; ante empate, menor costo y latencia. Revisá también la planilla de calidad antes de declarar un prompt ganador. Guardá el resultado seleccionado y su justificación en `prompts/EXPERIMENTS.md`. El piloto tiene sólo cinco ejemplos sintéticos por categoría, así que los scores orientan la siguiente iteración y no demuestran desempeño en producción.

## Prueba adversarial del filtro local

```powershell
python -m evals.input_guard --output data/reports/input_guard_latest.jsonl
$LASTEXITCODE
```

El comando imprime una fila JSON por caso y guarda una copia si indicás `--output`. `observed: "allowed"` indica que la consulta pasaría el filtro en el servicio. La prueba solo ejecuta el filtro, por lo que cada fila tiene `llm_calls: 0`. Si algún resultado difiere de lo esperado, el comando termina con código `1`.

El [reporte de ejemplo](../data/reports/input_guard_report.example.jsonl) contiene las cinco filas de la corrida inicial.
