# prompts/

Acá se guardarán versiones identificables de los prompts y el registro de experimentos. Cada comparación deberá indicar qué cambió y enlazar el resultado correspondiente en `data/reports/`. La técnica final se elegirá con evidencia de las evaluaciones.

`v1_zero_shot.yaml`, `v2-fewshot.yaml` y `v3-structured.yaml` son las tres variantes disponibles para el negocio. La CLI selecciona una con `--prompt`; si no se indica, usa `v1_zero_shot.yaml`. `v2-fewshot.yaml` añade ejemplos que el cargador incorpora a la instrucción del sistema.
