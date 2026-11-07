import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.llm.errors import LLMConfigurationError


@dataclass(frozen=True)
class PromptDefinition:
    prompt_id: str
    system_instruction: str


def load_prompt(path: Path) -> PromptDefinition:
    try:
        document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise LLMConfigurationError(f"No se pudo leer el prompt: {path}.") from error
    except yaml.YAMLError as error:
        raise LLMConfigurationError(f"El YAML del prompt no es válido: {path}.") from error

    if not isinstance(document, dict):
        raise LLMConfigurationError(f"El prompt debe contener un objeto YAML: {path}.")

    prompt_id = str(document.get("version") or path.stem).strip()
    system_instruction = document.get("system")
    if not isinstance(system_instruction, str) or not system_instruction.strip():
        raise LLMConfigurationError(
            f"El prompt debe definir una instrucción 'system': {path}."
        )

    examples = document.get("examples") or []
    if not isinstance(examples, list):
        raise LLMConfigurationError(f"'examples' debe ser una lista: {path}.")

    instruction = system_instruction.strip()
    if examples:
        formatted_examples = []
        for index, example in enumerate(examples, start=1):
            if not isinstance(example, dict) or "query" not in example or "response" not in example:
                raise LLMConfigurationError(
                    f"El ejemplo {index} debe incluir 'query' y 'response': {path}."
                )
            formatted_examples.append(
                "Consulta de ejemplo: "
                + str(example["query"])
                + "\nRespuesta JSON de ejemplo: "
                + json.dumps(example["response"], ensure_ascii=False, separators=(",", ":"))
            )
        instruction += "\n\nEjemplos de referencia:\n" + "\n\n".join(formatted_examples)

    return PromptDefinition(prompt_id=prompt_id, system_instruction=instruction)
