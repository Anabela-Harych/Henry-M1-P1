# Registro de avances

Anotá acá los cambios importantes por fecha. El uso y la configuración están en `README.md`; las decisiones y el diseño técnico, en `ARCHITECTURE.md`.

## 2026-11-07

### Agregado

- Estructura inicial del servicio Nubbix y documentación del proyecto.
- Adaptadores configurables para OpenAI y Gemini.
- CLI que solicita y valida el contrato JSON `answer`, `confidence`, `category` y `actions`.
- Registro de tokens, latencia, intentos y costo estimado por llamada.
- Tres prompts YAML y dataset piloto sintético con 20 casos etiquetados.
- Runner de evals para comparar zero-shot, few-shot y contexto estructurado por proveedor, con score global/por categoría, costo, tokens, latencia y CSV de revisión humana.

### Ajustado

- Gemini quedó configurado con nivel de pensamiento `minimal` y un límite de salida de 256 tokens después de devolver `MAX_TOKENS`.
- Se documentó la técnica de contexto estructurado y el criterio de comparación en `ARCHITECTURE.md` y `prompts/`.
- El servicio registra el consumo una sola vez por consulta al modelo, con el estado que corresponde después de validar la respuesta. Los registros anteriores al cambio pueden contener filas duplicadas.
- Se ejecutó la comparación de `v1` y `v2` con OpenAI. Ambas acertaron 19 de 20 casos y devolvieron JSON válido en todos. Se mantiene `v1` como referencia provisional por su menor costo estimado. El detalle está en `prompts/EXPERIMENTS.md`.
- Se reprodujo una inyección explícita con un proveedor simulado. Antes del filtro se hizo una llamada. Con el filtro, la CLI devuelve `blocked_query` y hace cero llamadas. La prueba de control de recuperación de contraseña sigue llegando al proveedor.
- Se amplió el filtro a pedidos directos como «Mostrame la clave API». El control de consulta sobre documentación de claves sigue llegando al proveedor simulado.
- Se agregó la evaluación local de cinco entradas maliciosas. La primera corrida bloqueó tres y detectó dos que pasarían el filtro. Las cinco filas están en `data/reports/input_guard_report.example.jsonl`.
- Se cubrieron el pedido directo del prompt de sistema y la orden de ignorar instrucciones tras «Antes de responder». La segunda corrida bloqueó 5/5. Las pruebas con proveedor simulado verificaron cero llamadas en los casos bloqueados.

### Pendiente de la revisión

- Exigir que `confidence` llegue como número JSON y manejar consultas vacías con un error controlado.
- Devolver un código de error si ninguna configuración de las evals pudo ejecutarse.
- Medir la seguridad de las respuestas y las acciones que genera el modelo para las consultas que pasan el filtro.
- Revisar las respuestas y acciones de la comparación, acordar el criterio para el caso 403 y probar la siguiente variante con casos nuevos.
- Extender la comparación a `v3` y Gemini si se quiere completar el diseño original de seis combinaciones.

