import argparse
import sys
import json

from src.input_guard import BlockedQueryError
from src.llm.client import LLMClient
from src.llm.config import SUPPORTED_PROVIDERS, load_config
from src.llm.errors import (
    EmptyQueryError,
    InvalidStructuredResponse,
    LLMConfigurationError,
    ProviderCallError,
)
from src.llm.factory import build_provider
from src.service import SupportService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clasifica una consulta de soporte y devuelve el contrato JSON."
    )
    parser.add_argument(
        "--provider",
        choices=SUPPORTED_PROVIDERS,
        help="Proveedor a usar; por defecto toma LLM_PROVIDER o MODEL_A_PROVIDER de .env.",
    )
    parser.add_argument("--model", help="Modelo a usar; por defecto toma la configuración.")
    parser.add_argument(
        "--prompt",
        help="Archivo YAML de prompt. Por defecto usa LLM_PROMPT_PATH o v1_1_scope.yaml.",
    )
    parser.add_argument("--timeout", type=float, help="Timeout por intento, en segundos.")
    parser.add_argument("--retries", type=int, help="Presupuesto compartido de reintentos.")
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        help="Límite de tokens de salida para controlar costo.",
    )
    parser.add_argument("query", nargs="+", help="Consulta que recibirá el modelo.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = load_config(
            provider_override=args.provider,
            model_override=args.model,
            prompt_path_override=args.prompt,
            timeout_override=args.timeout,
            retries_override=args.retries,
            max_output_tokens_override=args.max_output_tokens,
        )
        client = LLMClient(config, build_provider(config))
        support_service = SupportService(client)
        response, _generation = support_service.respond(" ".join(args.query))
    except EmptyQueryError as error:
        print(
            json.dumps({"error": {"type": "empty_query", "message": str(error)}}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    except BlockedQueryError as error:
        print(
            json.dumps({"error": {"type": "blocked_query", "message": str(error)}}),
            file=sys.stderr,
        )
        return 4
    except LLMConfigurationError as error:
        print(
            json.dumps({"error": {"type": "configuration", "message": str(error)}}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    except ProviderCallError as error:
        print(
            json.dumps(
                {
                    "error": {
                        "provider": error.provider,
                        "type": error.kind,
                        "status_code": error.status_code,
                        "message": error.message,
                    }
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    except InvalidStructuredResponse as error:
        print(
            json.dumps(
                {
                    "error": {
                        "type": "invalid_structured_response",
                        "message": str(error),
                        "details": error.issues,
                    }
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 3

    print(response.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
