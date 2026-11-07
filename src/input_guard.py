import re
import unicodedata


class BlockedQueryError(ValueError):
    """The input matched a local blocking rule."""


_OVERRIDE_INSTRUCTIONS = re.compile(
    r"(?:^|[.!?;\n])\s*"
    r"(?:(?:antes\s+de\s+responder|before\s+(?:you\s+)?(?:answer|respond))\s*,\s*)?"
    r"(?:"
    r"(?:ignora|omite|olvida|desobedece)\s+"
    r"(?:(?:todas\s+)?(?:tus|las)\s+)?(?:instrucciones|reglas)"
    r"|(?:ignore|disregard|forget)\s+"
    r"(?:(?:all|your|the|previous|prior|system)\s+)*(?:instructions|rules)"
    r")\b"
)

_DISCLOSE_PROTECTED_TEXT = re.compile(
    r"(?:^|[.!?;\n])\s*(?:"
    r"(?:por favor[,]?\s+)?"
    r"(?:mostra|mostrame|muestra|muestrame|dame|revela|revelame|imprime|imprimi|decime|dime)\s+"
    r"(?:(?:la|el|una|tu|mi)\s+)?"
    r"(?:clave\s+(?:de\s+)?api|prompt\s+(?:de|del)\s+sistema)"
    r"|(?:please\s+)?(?:show|reveal|print|give)\s+(?:me\s+)?"
    r"(?:(?:the|a|your|my)\s+)?(?:api[\s_-]+key|system[\s_-]+prompt)"
    r")\b"
)


def check_query(query: str) -> None:
    normalized = unicodedata.normalize("NFKD", query.casefold())
    plain_text = "".join(char for char in normalized if not unicodedata.combining(char))
    if _OVERRIDE_INSTRUCTIONS.search(plain_text) or _DISCLOSE_PROTECTED_TEXT.search(plain_text):
        raise BlockedQueryError("Consulta bloqueada por el filtro de entrada.")
