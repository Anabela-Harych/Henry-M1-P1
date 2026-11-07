import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def append_usage_event(path: Path, event: dict[str, Any]) -> None:
    """Append privacy-safe usage metadata; prompts and API keys are never logged."""
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:
        logger.warning("No se pudo guardar el registro de uso (%s).", type(error).__name__)
