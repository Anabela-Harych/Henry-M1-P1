# Registro de experimentos

## Comparación ejecutada con OpenAI

El 7 de noviembre de 2026 se compararon `triage-v1` (instrucciones directas) y `triage-v2-fewshot` (las mismas reglas más cuatro ejemplos). Se usó `gpt-6-luna` con el mismo esquema, límites y 20 consultas sintéticas por variante. Una prueba previa con un caso por categoría dio 4/4 aciertos y 4/4 salidas válidas por variante.

```powershell
python -m evals.runner --providers openai --prompts prompts/v1_zero_shot.yaml prompts/v2-fewshot.yaml --execute
```

La corrida usó `LLM_MAX_RETRIES=0` y generó el reporte local `data/reports/eval_20261107T210646Z.json`.

| Prompt | Aciertos | JSON válido | Tokens promedio entrada / salida | Latencia promedio | Costo total estimado |
|---|---:|---:|---:|---:|---:|
| `v1` | 19/20 (95 %) | 20/20 | 482,15 / 113,25 | 2,58 s | USD 0,0020968 |
| `v2` | 19/20 (95 %) | 20/20 | 797,15 / 92,60 | 2,18 s | USD 0,0025203 |

Ambos acertaron 5/5 en `billing`, `account` y `other`, y 4/5 en `technical`. Los dos clasificaron como `account` el código 403 al abrir informes (`NUB-SUP-TECH-005`), etiquetado como `technical` en el piloto. El caso merece revisar la regla de etiquetado porque el texto no aclara si es un problema de permisos o un fallo de la función.

**Decisión provisional.** Mantener `v1` como referencia para OpenAI. Con la misma exactitud y validez, se priorizó el costo estimado, que fue un 17 % menor. `v2` tuvo una latencia media 0,41 s menor en esta corrida. La elección queda sujeta a la revisión de las respuestas y acciones del CSV y a la prueba adversarial. Esta comparación abarca un modelo y un dataset sintético.

## Comparación inicial de context engineering

- Fecha UTC: 2026-11-07 (primer intento de corrida).
- Dataset: `data/datasets/eval_pilot.jsonl` (20 casos sintéticos; 5 por categoría).
- Proveedores/modelos: OpenAI `gpt-6-luna` y Gemini `gemini-3.6-flash`, según `.env`.
- Variantes: `triage-v1` (zero-shot), `triage-v2-fewshot` (ejemplos en contexto), `triage-v3-structured` (contexto por secciones).
- Diseño: mismo dataset, esquema y límites para todas las combinaciones; 120 llamadas en total.
- Criterio: priorizar tasa de contrato válido, después exactitud global y por categoría; en empate, revisar calidad manual y comparar costo/latencia.
- Resultado: no disponible. El entorno bloqueó conexiones de red; el log local registró errores de conexión de OpenAI sin tokens ni costo, y Gemini no llegó a devolver respuestas. No se selecciona un prompt con esta corrida.
- Seguimiento: la comparación de dos variantes con OpenAI quedó registrada arriba. La comparación con `v3` y Gemini queda pendiente.

