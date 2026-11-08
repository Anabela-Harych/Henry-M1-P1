import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

SENSITIVE_TEXT = re.compile(
    r"\b(?:[\w-]*api[ _-]?key|clave(?: de)? API|contrase[nñ]a|password|token|"
    r"c[oó]digo (?:de verificaci[oó]n|OTP)|CVV|CVC)\s*(?:[:=]|\bes\b)[^\r\n]*"
    r"|\bBearer\s+\S+"
    r"|\b(?:sk-|gsk_|AIza|ghp_|github_pat_)[\w-]+"
    r"|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b"
    r"|(?<!\w)\+?\d(?:[ ().-]*\d){6,}(?!\w)",
    re.IGNORECASE,
)


def redact_ticket(text: str, api_key: str) -> str:
    if api_key:
        text = text.replace(api_key, "[REDACTADO]")
    return SENSITIVE_TEXT.sub("[REDACTADO]", text)


def append_usage_event(path: Path, event: dict[str, Any]) -> None:
    """Append one usage record as JSONL."""
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
