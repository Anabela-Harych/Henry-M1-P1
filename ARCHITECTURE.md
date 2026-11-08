# Arquitectura

`CLI → servicio → filtro de entrada → cliente LLM → adaptador → proveedor → validación Pydantic → métricas y JSON`

## 1. Proveedores y control de llamadas

`src/main.py` carga la configuración de `.env` y las opciones de la CLI. `src/llm/factory.py` construye un adaptador bajo el contrato `LLMProvider`. OpenAI y Groq comparten el adaptador compatible con Responses API. Gemini tiene su propio adaptador. Cada ejecución usa el proveedor elegido, incluido cualquier reintento.

OpenAI queda como proveedor inicial por su cobertura en la evaluación. Gemini permite probar el mismo contrato con otro SDK y Groq aporta una opción para comparar costo y latencia. Los resultados están en el [README](README.md#extra-credit--comparativa-de-modelos).

| Parámetro | Decisión |
|---|---|
| Salida | 256 tokens por defecto para acotar el consumo de una respuesta breve. |
| Tiempo de espera | 30 segundos por intento para limitar la espera ante fallos. |
| Reintentos | Uno por defecto, compartido entre errores recuperables del proveedor y fallos del contrato. |
| Temperatura | Se conserva la predeterminada del proveedor. OpenAI mantiene el razonamiento predeterminado de Luna, Gemini usa `minimal` tras observar `MAX_TOKENS` y Groq usa `low` para dar más margen al JSON. |

`src/llm/client.py` controla los reintentos. Un `429` temporal, un `503` o un timeout pueden reintentarse. Los errores de autenticación o los límites permanentes de cuota identificados por el adaptador cierran la consulta.

`src/llm/telemetry.py` agrega una fila JSONL por consulta enviada al proveedor. Guarda el ticket con enmascarado de patrones sensibles, el resultado final, los tokens, la latencia total, los intentos y las tarifas aplicadas. Un error recuperado queda resumido en el número de intentos. El costo estimado es `(tokens de entrada × tarifa de entrada + tokens de salida × tarifa de salida) / 1.000.000`, con tarifas en USD por millón. Si falta consumo o tarifa, el costo queda en `null`.

## 2. Context engineering

`src/llm/prompt_loader.py` carga un YAML con una versión y una instrucción de sistema. El ticket se envía como entrada separada. `v1` da reglas directas, `v2` agrega ejemplos y `v3` divide las reglas en secciones. El [piloto de prompts](README.md#2-comparar-y-elegir-el-prompt) respalda la selección de `v1` con OpenAI.

## 3. Contrato de salida

`src/schemas.py` define `SupportResponse` con `answer`, `confidence`, `category` y `actions`. El adaptador envía su JSON Schema y `src/service.py` valida la respuesta localmente con Pydantic. Si el contrato falla, el cliente puede repetir una vez la consulta con el mismo esquema cuando queda presupuesto. Si se agota, la CLI emite `invalid_structured_response`.

## 4. Seguridad

`src/input_guard.py` detecta patrones de inyección y pedidos de secretos antes de llamar al modelo. El prompt indica cómo tratar el texto del ticket y proteger credenciales e instrucciones internas. Las acciones requieren decisión humana. La prueba adversarial mide cuántos ataques del dataset bloquea el filtro de entrada.

## 5. Evaluación

`evals/runner.py` evalúa combinaciones de proveedor y prompt sobre `data/datasets/eval_ticket_sup.jsonl`. Calcula *Exact Match* de categoría global y por categoría, validez del contrato, consumo, costo y latencia. El JSON guarda las respuestas y acciones por caso. `evals/input_guard.py` evalúa el filtro por separado con el dataset adversarial. Los [comandos de ejecución](README.md#5-ejecutar-las-evals-y-leer-el-reporte) están en el README.
