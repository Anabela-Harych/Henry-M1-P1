"""Compare versioned YAML prompts on the labeled support dataset."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.input_guard import BlockedQueryError
from src.llm.client import LLMClient
from src.llm.config import LLMConfig, load_config, normalize_provider
from src.llm.errors import (
    InvalidStructuredResponse,
    LLMConfigurationError,
    ProviderCallError,
)
from src.llm.factory import build_provider
from src.llm.models import GenerationResult
from src.service import SupportService


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "datasets" / "eval_pilot.jsonl"
DEFAULT_PROMPTS = [
    ROOT / "prompts" / "v1_zero_shot.yaml",
    ROOT / "prompts" / "v2-fewshot.yaml",
    ROOT / "prompts" / "v3-structured.yaml",
]
VALID_CATEGORIES = {"billing", "technical", "account", "other"}
REVIEW_FIELDS = [
    "case_id",
    "provider",
    "model",
    "prompt_id",
    "query",
    "expected_category",
    "predicted_category",
    "answer",
    "actions",
    "answer_criteria",
    "action_criteria",
    "must_not",
    "answer_relevant_0_or_1",
    "answer_safe_0_or_1",
    "actions_useful_0_or_1",
    "concise_0_or_1",
    "human_accept_0_or_1",
    "review_notes",
    "status",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compara prompts YAML con el dataset etiquetado de soporte."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Hace llamadas reales a los proveedores (pueden generar costo).",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=("openai", "gemini"),
        default=("openai", "gemini"),
        help="Proveedores a comparar; por defecto ambos.",
    )
    parser.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET, help="Archivo JSONL etiquetado."
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        type=Path,
        default=DEFAULT_PROMPTS,
        help="Archivos YAML de prompt que se compararán.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "data" / "reports"
    )
    parser.add_argument(
        "--limit-per-category",
        type=int,
        help="Limita casos por categoría para una corrida piloto más corta.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        help="Sobrescribe el límite de salida configurado en .env.",
    )
    return parser


def load_dataset(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"No se pudo leer el dataset: {path}.") from error

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"JSON inválido en la línea {line_number} del dataset.") from error
        if not isinstance(case, dict):
            raise ValueError(f"La línea {line_number} debe ser un objeto JSON.")
        required = ("id", "query", "expected_category")
        if any(not isinstance(case.get(key), str) or not case[key].strip() for key in required):
            raise ValueError(
                f"La línea {line_number} debe incluir id, query y expected_category."
            )
        if case["expected_category"] not in VALID_CATEGORIES:
            raise ValueError(f"Categoría inválida en la línea {line_number}.")
        for field in ("answer_criteria", "action_criteria", "must_not"):
            if not isinstance(case.get(field, []), list):
                raise ValueError(f"{field} debe ser una lista en la línea {line_number}.")
        cases.append(case)

    if not cases:
        raise ValueError("El dataset no contiene casos.")
    return cases


def select_cases(
    cases: list[dict[str, Any]], limit_per_category: int | None
) -> list[dict[str, Any]]:
    if limit_per_category is None:
        return cases
    if limit_per_category < 1:
        raise ValueError("--limit-per-category debe ser mayor que cero.")
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for case in cases:
        category = case["expected_category"]
        if counts[category] < limit_per_category:
            selected.append(case)
            counts[category] += 1
    return selected


def build_plan(
    providers: list[str], prompts: list[Path], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    for case in cases:
        counts[case["expected_category"]] += 1
    return {
        "mode": "plan",
        "providers": providers,
        "prompts": [str(path) for path in prompts],
        "cases": len(cases),
        "cases_by_category": dict(sorted(counts.items())),
        "planned_api_calls": len(providers) * len(prompts) * len(cases),
        "note": "Sin --execute no se leen claves ni se realizan llamadas.",
    }


def config_for(
    provider: str, prompt_path: Path, max_output_tokens: int | None
) -> LLMConfig:
    return load_config(
        provider_override=provider,
        prompt_path_override=prompt_path,
        max_output_tokens_override=max_output_tokens,
    )


def base_result(
    case: dict[str, Any], config: LLMConfig | None, provider: str, prompt_path: Path
) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "expected_category": case["expected_category"],
        "provider": provider,
        "model": config.model if config else None,
        "prompt_id": config.prompt_id if config else prompt_path.stem,
        "prompt_file": prompt_path.name,
        "status": "not_run",
        "contract_valid": False,
        "predicted_category": None,
        "category_correct": False,
        "confidence": None,
        "answer": None,
        "actions": None,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "latency_ms": None,
        "attempts": None,
        "estimated_cost_usd": None,
        "cost_basis": None,
        "finish_reason": None,
        "error_type": None,
        "error_details": None,
    }


def generation_metrics(result: dict[str, Any], generation: GenerationResult) -> None:
    result.update(
        {
            "input_tokens": generation.input_tokens,
            "output_tokens": generation.output_tokens,
            "total_tokens": generation.total_tokens,
            "latency_ms": generation.latency_ms,
            "attempts": generation.attempts,
            "estimated_cost_usd": generation.estimated_cost_usd,
            "cost_basis": generation.cost_basis,
            "finish_reason": generation.finish_reason,
        }
    )


def evaluate_one(
    service: SupportService, case: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response, generation = service.respond(case["query"])
        result.update(
            {
                "status": "success",
                "contract_valid": True,
                "predicted_category": response.category,
                "category_correct": response.category == case["expected_category"],
                "confidence": response.confidence,
                "answer": response.answer,
                "actions": response.actions,
            }
        )
        generation_metrics(result, generation)
    except BlockedQueryError:
        result.update(
            {
                "status": "blocked_query",
                "error_type": "blocked_query",
                "attempts": 0,
            }
        )
    except InvalidStructuredResponse as error:
        result.update(
            {
                "status": "invalid_contract",
                "error_type": "invalid_structured_response",
                "error_details": error.issues,
            }
        )
        if isinstance(error.generation, GenerationResult):
            generation_metrics(result, error.generation)
    except ProviderCallError as error:
        result.update(
            {
                "status": "provider_error",
                "error_type": error.kind,
                "error_details": {"status_code": error.status_code},
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    except Exception as error:
        # Keep one unexpected SDK/transport failure from discarding the rest of
        # the run. Store the exception class only; SDK messages can contain data.
        result.update(
            {
                "status": "unexpected_error",
                "error_type": type(error).__name__,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    return result


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def summarize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        groups[
            (
                result["provider"],
                result["model"] or "unavailable",
                result["prompt_id"],
                result["expected_category"],
            )
        ].append(result)

    summaries: list[dict[str, Any]] = []
    by_configuration: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (provider, model, prompt_id, category), rows in groups.items():
        by_configuration[(provider, model, prompt_id)].extend(rows)
        summaries.append(_summary_row(provider, model, prompt_id, category, rows))
    for (provider, model, prompt_id), rows in by_configuration.items():
        summaries.append(_summary_row(provider, model, prompt_id, None, rows))
    summaries.sort(
        key=lambda row: (
            row["provider"],
            row["model"],
            row["prompt_id"],
            row["category"] is None,
            row["category"] or "",
        )
    )
    return summaries


def _summary_row(
    provider: str,
    model: str,
    prompt_id: str,
    category: str | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    correct = sum(bool(row["category_correct"]) for row in rows)
    valid = sum(bool(row["contract_valid"]) for row in rows)
    latencies = [row["latency_ms"] for row in rows if row["latency_ms"] is not None]
    input_tokens = [row["input_tokens"] for row in rows if row["input_tokens"] is not None]
    output_tokens = [row["output_tokens"] for row in rows if row["output_tokens"] is not None]
    total_tokens = [row["total_tokens"] for row in rows if row["total_tokens"] is not None]
    costs = [row["estimated_cost_usd"] for row in rows if row["estimated_cost_usd"] is not None]
    tokenized_calls = sum(
        row["input_tokens"] is not None and row["output_tokens"] is not None
        for row in rows
    )
    cost_bases = sorted({row["cost_basis"] for row in rows if row["cost_basis"]})
    cost_coverage = len(costs) / len(rows) if rows else 0.0
    total_cost = round(sum(costs), 10) if costs else None
    cost_status = (
        "unavailable"
        if not costs
        else "complete"
        if len(costs) == len(rows)
        else "partial"
    )
    return {
        "provider": provider,
        "model": model,
        "prompt_id": prompt_id,
        "category": category,
        "n_cases": len(rows),
        # Invalid or failed outputs count as incorrect in the end-to-end score.
        "score_category_accuracy": round(correct / len(rows), 4) if rows else None,
        "contract_valid_rate": round(valid / len(rows), 4) if rows else None,
        "valid_responses": valid,
        "correct_categories": correct,
        "avg_input_tokens": _mean(input_tokens),
        "avg_output_tokens": _mean(output_tokens),
        "avg_total_tokens": _mean(total_tokens),
        "avg_latency_ms": _mean(latencies),
        "estimated_cost_usd_total": total_cost,
        "estimated_cost_usd_avg_per_call": (
            round(sum(costs) / len(costs), 10) if costs else None
        ),
        "estimated_cost_usd_avg_per_case": (
            round(sum(costs) / len(rows), 10) if len(costs) == len(rows) else None
        ),
        "costed_calls": len(costs),
        "tokenized_calls": tokenized_calls,
        "cost_coverage_rate": round(cost_coverage, 4),
        "cost_estimate_status": cost_status,
        "cost_basis": cost_bases,
        # Retain the earlier summary field names for any local analysis scripts.
        "total_estimated_cost_usd": total_cost,
        "avg_cost_per_case_usd": (
            round(sum(costs) / len(rows), 10) if len(costs) == len(rows) else None
        ),
    }


def _format_usd(value: float | None) -> str:
    return f"${value:.8f} USD" if value is not None else "Sin datos de tokens"


def render_analysis_markdown(
    summaries: list[dict[str, Any]], run_id: str, cases_count: int
) -> str:
    overall = [row for row in summaries if row["category"] is None]
    categories = [row for row in summaries if row["category"] is not None]
    lines = [
        f"# Análisis de evals — {run_id}",
        "",
        f"Casos por combinación de modelo y prompt: {cases_count}.",
        "El costo es una estimación en USD a partir de tokens reportados y la tarifa registrada; no es el cargo final del proveedor.",
        "",
        "## Resumen global por proveedor y prompt",
        "",
        "| Proveedor | Modelo | Prompt | Score categoría | Contrato válido | Tokens entrada/salida prom. | Latencia prom. (ms) | Costo total estimado | Costo prom. por llamada con tokens | Cobertura del costo | Base de tarifa |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in overall:
        score = "—" if row["score_category_accuracy"] is None else f"{row['score_category_accuracy']:.1%}"
        contract = "—" if row["contract_valid_rate"] is None else f"{row['contract_valid_rate']:.1%}"
        tokens = (
            f"{row['avg_input_tokens']} / {row['avg_output_tokens']}"
            if row["avg_input_tokens"] is not None or row["avg_output_tokens"] is not None
            else "—"
        )
        latency = "—" if row["avg_latency_ms"] is None else f"{row['avg_latency_ms']:.1f}"
        coverage = f"{row['costed_calls']}/{row['n_cases']}"
        basis = ", ".join(row["cost_basis"]) or "—"
        lines.append(
            f"| {row['provider']} | {row['model']} | {row['prompt_id']} | {score} | {contract} | {tokens} | {latency} | {_format_usd(row['estimated_cost_usd_total'])} | {_format_usd(row['estimated_cost_usd_avg_per_call'])} | {coverage} | {basis} |"
        )

    lines.extend(
        [
            "",
            "## Score y costo estimado por categoría",
            "",
            "| Proveedor | Modelo | Prompt | Categoría | Score categoría | Contrato válido | Costo total estimado (USD) | Cobertura del costo |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in categories:
        score = "—" if row["score_category_accuracy"] is None else f"{row['score_category_accuracy']:.1%}"
        contract = "—" if row["contract_valid_rate"] is None else f"{row['contract_valid_rate']:.1%}"
        coverage = f"{row['costed_calls']}/{row['n_cases']}"
        lines.append(
            f"| {row['provider']} | {row['model']} | {row['prompt_id']} | {row['category']} | {score} | {contract} | {_format_usd(row['estimated_cost_usd_total'])} | {coverage} |"
        )

    if not any(row["costed_calls"] for row in summaries):
        has_token_usage = any(row["tokenized_calls"] for row in overall)
        explanation = (
            "Hay tokens de uso, pero no una tarifa conocida para ese modelo. Definí ambos "
            "precios por millón en .env o agregá la tarifa del modelo en src/llm/pricing.py."
            if has_token_usage
            else "No hubo tokens de uso disponibles para calcular el costo. Revisá los estados de las llamadas en el JSON y el log de uso."
        )
        lines.extend(
            [
                "",
                explanation,
            ]
        )
    elif any(row["cost_estimate_status"] != "complete" for row in overall):
        lines.extend(
            [
                "",
                "Hay llamadas sin tokens reportados. El costo total suma sólo llamadas con uso conocido; la cobertura muestra cuántas pudieron calcularse.",
            ]
        )
    return "\n".join(lines) + "\n"


def write_reports(
    output_dir: Path,
    run_id: str,
    dataset_path: Path,
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    providers: list[str],
    prompts: list[Path],
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(results)
    report_path = output_dir / f"eval_{run_id}.json"
    review_path = output_dir / f"eval_{run_id}_review.csv"
    analysis_path = output_dir / f"eval_{run_id}_analysis.md"
    report = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "providers": providers,
        "prompts": [path.name for path in prompts],
        "score_definition": (
            "La accuracy de categoría es correctas/casos totales; respuestas inválidas "
            "o fallidas cuentan como incorrectas."
        ),
        "summaries": summary,
        "results": results,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    analysis_path.write_text(
        render_analysis_markdown(summary, run_id, len(cases)), encoding="utf-8"
    )

    case_by_id = {case["id"]: case for case in cases}
    with review_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for result in results:
            case = case_by_id[result["case_id"]]
            writer.writerow(
                {
                    "case_id": result["case_id"],
                    "provider": result["provider"],
                    "model": result["model"],
                    "prompt_id": result["prompt_id"],
                    "query": case["query"],
                    "expected_category": result["expected_category"],
                    "predicted_category": result["predicted_category"],
                    "answer": result["answer"],
                    "actions": json.dumps(result["actions"], ensure_ascii=False),
                    "answer_criteria": " | ".join(case.get("answer_criteria", [])),
                    "action_criteria": " | ".join(case.get("action_criteria", [])),
                    "must_not": " | ".join(case.get("must_not", [])),
                    "answer_relevant_0_or_1": "",
                    "answer_safe_0_or_1": "",
                    "actions_useful_0_or_1": "",
                    "concise_0_or_1": "",
                    "human_accept_0_or_1": "",
                    "review_notes": "",
                    "status": result["status"],
                }
            )
    return report_path, review_path, analysis_path


def main() -> int:
    args = build_parser().parse_args()
    try:
        providers = [normalize_provider(provider) for provider in args.providers]
        prompts = [path if path.is_absolute() else ROOT / path for path in args.prompts]
        dataset_path = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
        cases = select_cases(load_dataset(dataset_path), args.limit_per_category)
    except (LLMConfigurationError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2

    plan = build_plan(providers, prompts, cases)
    if not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    usage_path = output_dir / f"eval_{run_id}_usage.jsonl"
    os.environ["LLM_USAGE_LOG_PATH"] = str(usage_path)
    results: list[dict[str, Any]] = []

    for provider in providers:
        for prompt_path in prompts:
            try:
                config = config_for(provider, prompt_path, args.max_output_tokens)
                service = SupportService(LLMClient(config, build_provider(config)))
            except Exception as error:
                for case in cases:
                    row = base_result(case, None, provider, prompt_path)
                    row.update(
                        {
                            "status": "configuration_error",
                            "error_type": (
                                "configuration"
                                if isinstance(error, LLMConfigurationError)
                                else type(error).__name__
                            ),
                            "error_details": (
                                str(error)
                                if isinstance(error, LLMConfigurationError)
                                else None
                            ),
                        }
                    )
                    results.append(row)
                continue

            for case in cases:
                row = base_result(case, config, provider, prompt_path)
                results.append(evaluate_one(service, case, row))

    report_path, review_path, analysis_path = write_reports(
        output_dir, run_id, dataset_path, cases, results, providers, prompts
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "planned_api_calls": plan["planned_api_calls"],
                "report": str(report_path),
                "analysis": str(analysis_path),
                "manual_review": str(review_path),
                "usage_log": str(usage_path),
                "summaries": summarize(results),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
