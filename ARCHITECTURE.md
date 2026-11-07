# Arquitectura

## Estado

Flujo principal implementado: CLI, adaptadores para OpenAI y Gemini, salida JSON estructurada validada, límites de llamada y registro de uso. `python -m evals.runner --execute` compara las versiones de prompt sobre el dataset etiquetado y genera resultados globales y por categoría.

## Flujo previsto

1. La CLI recibe una consulta y el proveedor elegido por `--provider` o `.env`.
2. La fábrica selecciona el adaptador común de OpenAI o Gemini y aplica el prompt de sistema versionado.
3. El adaptador envía la consulta, la instrucción del prompt y el esquema JSON usando el SDK oficial.
4. La capa común aplica el límite de reintentos y mide latencia total.
5. El servicio valida localmente la respuesta antes de serializar los cuatro campos del contrato.
6. Se estima el costo y se registra metadato de uso, sin guardar la consulta ni la respuesta.

## Contrato de salida

La respuesta tendrá cuatro campos:

- `answer`: texto para el usuario.
- `confidence`: número entre `0.0` y `1.0`. Se considera una señal de confianza del modelo, no una probabilidad calibrada hasta medir su calibración.
- `category`: uno de `billing`, `technical`, `account` o `other`.
- `actions`: lista de acciones sugeridas para el agente humano; no se ejecutan automáticamente.

La salida debe fallar de forma controlada si falta un campo o la categoría no pertenece al conjunto permitido.

## Componentes previstos

- `src/`: punto de entrada CLI, esquema del contrato, servicio, fábrica y adaptadores OpenAI/Gemini, límites, estimación de costo y telemetría.
- `prompts/`: versiones comparables del prompt y notas de cada experimento.
- `data/datasets/`: ejemplos etiquetados para evaluación y, opcionalmente, casos adversariales.
- `evals/`: ejecución del dataset, métricas globales y por categoría, y generación de reportes.
- `tests/`: pruebas del contrato, serialización y componentes locales.
- `data/reports/`: resultados generados; no se guardan secretos en ellos.

## Context engineering y evidencia

La técnica aplicada en `prompts/v3-structured.yaml` es estructurar el contexto en secciones con funciones distintas: rol y alcance, confianza en los datos de entrada, reglas de clasificación, criterios de respuesta y contrato de salida. Esto hace explícito qué información es instrucción, qué contenido es dato no confiable y cómo resolver ambigüedades. También permite modificar una parte de la política sin mezclarla con el formato de salida. El prompt se mantiene en YAML y se carga fuera del código.

Para medir el efecto, `evals/runner.py` compara esa versión con `v1_zero_shot.yaml` (instrucción base) y `v2-fewshot.yaml` (la misma base más ejemplos en contexto). Los modelos de la comparación son OpenAI `gpt-6-luna` y Gemini `gemini-3.6-flash`. Cada variante se aplica a los mismos casos, con el mismo esquema de salida y límites de llamada; se reportan resultados por modelo y prompt para no confundir el efecto del proveedor con el del contexto.

El score global y por categoría es exactitud de clasificación sobre todos los casos; una salida inválida o un error cuenta como incorrecto. Se informa por separado la tasa de contrato válido, tokens, latencia y costo estimado. Las respuestas y acciones se revisan además con los criterios etiquetados del dataset: pertinencia, seguridad, utilidad, concisión y aceptación. La decisión por modelo prioriza validez del contrato y exactitud; los empates se resuelven por costo y latencia, después de revisar la calidad de las respuestas. La corrida reproducible y la selección quedan registradas en `prompts/EXPERIMENTS.md`.

El dataset `data/datasets/eval_pilot.jsonl` contiene veinte casos sintéticos, cinco por categoría. Los resultados justifican una elección inicial para continuar el proyecto, no una afirmación de desempeño en producción; antes de esa conclusión hay que ampliar y revisar el conjunto con casos representativos del negocio.

## Seguridad y límites

- El servicio aplica un filtro local a la entrada antes de llamar al proveedor. Una orden explícita para ignorar instrucciones puede producir el error `blocked_query`. Las pruebas cubren patrones en español e inglés y un control legítimo de recuperación de contraseña.
- Las acciones son recomendaciones para una persona; el servicio no realiza cambios en cuentas ni cobros.
- Las claves se leen desde variables locales y nunca se registran en prompts, reportes o control de versiones.
- Los reintentos son acotados, se aplican solo a fallos transitorios y no se realizan para errores de configuración o autenticación.
- El límite de tokens y el timeout acotan la salida y la duración de cada llamada. La estimación de costo usa tarifas configurables y no reemplaza la factura del proveedor.
- En Gemini, el nivel de pensamiento se configura por separado porque sus tokens cuentan dentro del límite de salida. El valor inicial es `minimal` para este flujo de clasificación.
- El registro de uso guarda proveedor, modelo, tokens, latencia, intentos y costo estimado, sin guardar texto de entrada ni salida.
- La suite adversarial local prueba cinco consultas sintéticas y reporta el resultado del filtro por separado de las evals del modelo.
