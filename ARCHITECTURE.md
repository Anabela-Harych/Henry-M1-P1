# Arquitectura

## Estado

Flujo principal inicial implementado: CLI, adaptadores para OpenAI y Gemini, salida JSON estructurada validada, límites de llamada y registro de uso. Las evals siguen pendientes.

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

Los modelos elegidos para la comparación inicial son OpenAI `gpt-6-luna` y Gemini `gemini-3.6-flash`. Se deben ejecutar sobre los mismos casos y con la misma versión de prompt para separar el efecto del modelo del efecto del prompting.

La técnica de context engineering queda pendiente de experimentación. Se partirá de una versión base y se comparará con alternativas documentadas en `prompts/`. La decisión se justificará con resultados reproducibles: score global y por categoría, validez del contrato, comportamiento ante entradas adversariales, tokens, latencia y costo. No se afirmará una mejora sin registrar la corrida y sus datos.

El dataset `data/datasets/eval_pilot.jsonl` es sintético y sirve para iniciar el diseño de evals; debe revisarse y ampliarse con ejemplos representativos del dominio real antes de sacar conclusiones.

## Seguridad y límites

- Las acciones son recomendaciones para una persona; el servicio no realiza cambios en cuentas ni cobros.
- Las claves se leen desde variables locales y nunca se registran en prompts, reportes o control de versiones.
- Los reintentos son acotados, se aplican solo a fallos transitorios y no se realizan para errores de configuración o autenticación.
- El límite de tokens y el timeout acotan la salida y la duración de cada llamada. La estimación de costo usa tarifas configurables y no reemplaza la factura del proveedor.
- En Gemini, el nivel de pensamiento se configura por separado porque sus tokens cuentan dentro del límite de salida. El valor inicial es `minimal` para este flujo de clasificación.
- El registro de uso guarda proveedor, modelo, tokens, latencia, intentos y costo estimado, sin guardar texto de entrada ni salida.
- La suite adversarial opcional tendrá diez consultas maliciosas y reportará sus resultados por separado.
