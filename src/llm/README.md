# Integración de proveedores

La interfaz común está en `src/llm/client.py`. `src/llm/factory.py` crea el adaptador según el proveedor seleccionado, y los adaptadores convierten las respuestas y errores propios de cada SDK al formato compartido.

## Proveedores configurados

- OpenAI: modelo predeterminado de esta comparación, `gpt-6-luna`.
- Gemini: modelo predeterminado de esta comparación, `gemini-3.6-flash`.

Se pueden seleccionar con `--provider openai` o `--provider gemini`. El nombre del modelo se toma de `OPENAI_MODEL`/`GEMINI_MODEL`, o de los pares `MODEL_A_PROVIDER`/`MODEL_A_NAME` y `MODEL_B_PROVIDER`/`MODEL_B_NAME`. La clave Gemini se puede llamar `GEMINI_API_KEY` o `GOOGLE_API_KEY`.

Ambos adaptadores reciben la instrucción de la versión YAML seleccionada con `--prompt` o `LLM_PROMPT_PATH`. El cargador agrega los ejemplos de `v2-fewshot.yaml` al contexto. La salida se restringe con el esquema del contrato y se valida localmente; `LLM_MAX_OUTPUT_TOKENS` limita la generación.

## Límites y errores

- Timeout por intento configurable con `LLM_TIMEOUT_SECONDS` (por defecto 30 s).
- Máximo de reintentos configurables con `LLM_MAX_RETRIES` (por defecto 1; admite 0–5). Los SDK no reintentan por su cuenta.
- Solo se reintentan fallos transitorios. Los errores de autenticación, configuración, cuota agotada o solicitud inválida fallan sin reintentar.
- `LLM_MAX_OUTPUT_TOKENS` limita el máximo de salida (por defecto 256).
- Gemini usa `GEMINI_THINKING_LEVEL=minimal` por defecto para dejar más presupuesto de tokens a la respuesta; se puede cambiar a `low`, `medium` o `high`.
- El tiempo registrado incluye todos los intentos y las esperas entre ellos.

## Uso y costo

Cada llamada registra tokens de entrada/salida, latencia, intentos, prompt y costo estimado en `data/reports/llm_usage.jsonl`; el archivo no contiene el prompt, la salida ni las claves. La CLI imprime solo los cuatro campos del contrato.

La tarifa de referencia en `pricing.py` corresponde a Standard pago y fue consultada el 2026-11-07. El precio de Gemini 3.6 Flash publicado para Standard pago cambia el 2027-01-01; los precios pueden variar por plan o modalidad. Se pueden sobrescribir con las variables de precio de `.env.example`. Modelos desconocidos sin precios configurados producen `estimated_cost_usd: null`.

El límite de salida, los reintentos acotados y la estimación ayudan a controlar el consumo; todavía no hay un presupuesto total diario/mensual que bloquee llamadas. Si una conexión se corta después de que el proveedor procesó la consulta, puede haber un cargo sin metadatos de uso disponibles localmente. Contrastá esos casos con el panel de consumo del proveedor.
