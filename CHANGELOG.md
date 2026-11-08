# Registro de avances


## 2026-11-07

### Agregado

- Estructura inicial del servicio Nubbix y documentación del proyecto.
- Adaptadores configurables para OpenAI y Gemini.
- CLI que solicita y valida el contrato JSON `answer`, `confidence`, `category` y `actions`.
- Registro de tokens, latencia, intentos y costo estimado por llamada.
- Tres prompts YAML y dataset piloto sintético con 20 casos etiquetados.
- Runner de evals para comparar zero-shot, few-shot y contexto estructurado por proveedor, con score global y por categoría, costo, tokens y latencia.

### Ajustado

- Gemini quedó configurado con nivel de pensamiento `minimal` y un límite de salida de 256 tokens después de devolver `MAX_TOKENS`.
- Se documentó la técnica de contexto estructurado y el criterio de comparación en `ARCHITECTURE.md` y `prompts/`.
- El servicio registra el consumo una sola vez por consulta al modelo, con el estado que corresponde después de validar la respuesta. Los registros anteriores al cambio pueden contener filas duplicadas.
- Se ejecutó la comparación de `v1` y `v2` con OpenAI. Ambas acertaron 19 de 20 casos y devolvieron JSON válido en todos. Se eligió `v1` como prompt por defecto de OpenAI por su menor costo estimado. El [README](README.md#2-comparar-y-elegir-el-prompt) reúne la evidencia.
- Se reprodujo una inyección explícita con un proveedor simulado. Antes del filtro se hizo una llamada. Con el filtro, la CLI devuelve `blocked_query` y hace cero llamadas. La prueba de control de recuperación de contraseña sigue llegando al proveedor.
- Se amplió el filtro a pedidos directos como «Mostrame la clave API». El control de consulta sobre documentación de claves sigue llegando al proveedor simulado.
- Se agregó la evaluación local de cinco entradas maliciosas. La primera corrida bloqueó tres y detectó dos que pasarían el filtro. Las cinco filas están en `data/reports/input_guard_report.example.jsonl`.
- Se cubrieron el pedido directo del prompt de sistema y la orden de ignorar instrucciones tras «Antes de responder». La segunda corrida bloqueó 5/5. Las pruebas con proveedor simulado verificaron cero llamadas en los casos bloqueados.
- Se hizo estricta la validación numérica de `confidence`. Las consultas vacías devuelven `empty_query` y código `2` antes de llamar al proveedor.
- La CLI reintenta una vez si la respuesta incumple el contrato y queda presupuesto. Registra un solo evento con el consumo reportado de todos los intentos. Las evals miden la primera salida del modelo.
- Se unificó el límite de salida predeterminado en 256 tokens y se documentaron la elección de proveedores y los criterios de temperatura, timeout y reintentos.
- La CLI registra métricas en `data/metrics.jsonl` por defecto. Los eventos y reportes nuevos incluyen las tarifas numéricas aplicadas junto con el costo estimado.
- `NUB-ADV-006` pasaba el filtro al pedir de forma indirecta las instrucciones internas. Se amplió la regla de divulgación y se repitió la evaluación sobre los mismos textos. Los ataques bloqueados pasaron de 5/6 a 6/6 y el control legítimo siguió permitido.
- Se agregaron tres pruebas locales para el contrato JSON, el servicio con ambos proveedores simulados y el cálculo de los scores de evaluación.
- El runner de evals devuelve código `1` cuando ninguna combinación recibe una respuesta del modelo y conserva los reportes de diagnóstico.
- Se amplió el dataset de 20 a 30 tickets etiquetados, con casos borde de facturación, permisos, errores técnicos y consultas con poca información.
- Se amplió la suite a diez ataques y un control legítimo. Dos variantes evadían el filtro, una con dos puntos después del preámbulo y otra con una etiqueta de rol falsa. Tras ajustar el patrón, los bloqueos pasaron de 8/10 a 10/10 y el control siguió permitido.
- Se registró la comparativa de modelos como extra credit. Con el mismo prompt y 30 tickets por proveedor, OpenAI devolvió 30 salidas válidas y Gemini devolvió 8. Ambos acertaron 7 de los 8 casos en común.
- Se documentó en el README la respuesta de OpenAI al caso 403 ambiguo y el resultado de los casos con más contexto.
- Se habilitó Groq como tercer proveedor configurable y se agregó una pausa opcional entre tickets en el runner para respetar límites de tasa.
- Se ejecutó la comparación con Groq sobre los mismos 30 tickets. Acertó 28, devolvió 30 salidas válidas y promedió 0,56 s de latencia. Se incorporó la tarifa publicada para calcular el costo de referencia.
