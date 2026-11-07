# data/datasets/

`eval_pilot.jsonl` inicia el dataset de evaluación con veinte casos sintéticos: cinco por categoría. Cada línea incluye un identificador, consulta, categoría esperada, criterios para la respuesta y las acciones, y aspectos que no debe inventar. Los IDs siguen el formato `NUB-SUP-{CATEGORIA}-{N}` como referencias internas del piloto; no son números de tickets reales de Nubbix. Es un piloto; debe revisarse y crecer con ejemplos representativos del dominio real antes de usar sus scores como conclusión.

La suite opcional de resistencia adversarial tendrá diez entradas maliciosas en un archivo separado, para distinguirla del conjunto normal.
