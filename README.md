# Servicio de clasificación de consultas

## Estado

Está implementado el flujo principal inicial: una consulta por CLI pasa por el proveedor configurable y devuelve el contrato JSON validado. La suite de evals todavía no está implementada.

## Objetivo

Recibir una consulta de soporte en texto libre y preparar una respuesta JSON validada con el contrato:

- `answer`: respuesta sugerida.
- `confidence`: nivel de confianza entre `0.0` y `1.0`; no se tratará como probabilidad calibrada sin medirlo.
- `category`: `billing`, `technical`, `account` u `other`.
- `actions`: lista de acciones sugeridas para el agente humano.

Las acciones son sugerencias: el servicio no las ejecuta.

## Estructura

```text
src/                 CLI y lógica del servicio
prompts/             Prompts versionados y registro de experimentos
data/datasets/       Dataset etiquetado y casos adversariales
data/reports/         Reportes generados por las evaluaciones
evals/                Ejecución y métricas de evaluación
tests/                Pruebas del contrato y del comportamiento del código
ARCHITECTURE.md       Componentes, flujo y decisiones técnicas
requirements.txt      Dependencias de Python
.env.example          Variables de entorno de ejemplo
.env                  Configuración local; no se sube a Git
```

## Preparar el entorno

En PowerShell, desde la raíz del proyecto:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Completá `.env` con los nombres de los dos modelos elegidos y las claves de sus proveedores. No compartas ni subas ese archivo.

## Probar la conexión a un proveedor

Desde la raíz, elegí el proveedor configurado. Se puede seleccionar cualquiera de los tres prompts YAML con `--prompt`.

```powershell
python -m src.main --provider openai "Necesito ayuda con mi cuenta"
python -m src.main --provider gemini "Necesito ayuda con mi cuenta"
python -m src.main --provider openai --prompt prompts/v2-fewshot.yaml "Me cobraron dos veces"
```

La CLI solicita JSON con esquema estructurado al proveedor y valida localmente `answer`, `confidence`, `category` y `actions` antes de imprimir. Limita tokens de salida, timeout y reintentos con los valores de `.env`. Cada ejecución guarda proveedor, modelo, versión de prompt, tokens, latencia, intentos y costo estimado en `data/reports/llm_usage.jsonl`. No registra la consulta ni la respuesta en ese archivo.

El costo es una estimación con tarifas Standard pagas de referencia para los dos modelos configurados. Puede diferir si usás un nivel gratuito, otro procesamiento o cambian las tarifas. Los cuatro valores `*_USD_PER_MILLION_TOKENS` permiten ajustarlas; si el modelo no tiene una tarifa conocida o configurada, el costo queda como `null`.

## Evaluación

La suite todavía no está implementada. `data/datasets/eval_pilot.jsonl` contiene un piloto sintético con cinco casos por categoría. La estructura prevé medir el score global y por categoría. La técnica de context engineering se elegirá y justificará después de comparar resultados reproducibles.
