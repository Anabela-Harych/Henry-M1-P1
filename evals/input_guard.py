import argparse
import json
import sys
from pathlib import Path

from src.input_guard import BlockedQueryError, check_query


DATASET = Path(__file__).resolve().parents[1] / "data/datasets/input_guard_adversarial.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba el filtro local con entradas adversariales.")
    parser.add_argument("--output", type=Path, help="También guarda el reporte JSONL en esta ruta.")
    args = parser.parse_args()

    rows = []
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        try:
            check_query(case["query"])
        except BlockedQueryError:
            observed = "blocked"
        else:
            observed = "allowed"

        rows.append(
            {
                **case,
                "observed": observed,
                "passed": observed == case["expected"],
                "llm_calls": 0,
            }
        )

    report = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")

    passed = sum(row["passed"] for row in rows)
    print(f"Expectativas cumplidas: {passed}/{len(rows)}. Llamadas al LLM: 0.", file=sys.stderr)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
