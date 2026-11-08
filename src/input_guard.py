import re
import unicodedata


class BlockedQueryError(ValueError):
    """The input matched a local blocking rule."""


_COMMAND_START = (
    r"(?:^|[.!?;\n])\s*"
    r"(?:\[(?:system|developer|sistema|desarrollador)\](?:\s*:)?\s*)?"
)

_OVERRIDE_INSTRUCTIONS = re.compile(
    _COMMAND_START
    + r"(?:(?:antes\s+de\s+responder|before\s+(?:you\s+)?(?:answer|respond))\s*[,:]\s*)?"
    r"(?:"
    r"(?:ignora|omite|olvida|desobedece)\s+"
    r"(?:(?:todas\s+)?(?:tus|las)\s+)?(?:instrucciones|reglas)"
    r"|(?:ignore|disregard|forget)\s+"
    r"(?:(?:all|your|the|previous|prior|system)\s+)*(?:instructions|rules)"
    r")\b"
)

_DISCLOSE_PROTECTED_TEXT = re.compile(
    _COMMAND_START
    + r"(?:[¿¡]\s*)?(?:"
    r"(?:por\s+favor[,]?\s+)?(?:(?:me\s+)?(?:podrias|puedes|podes)\s+)?"
    r"(?:mostra|mostrame|muestra|muestrame|mostrar|mostrarme|dame"
    r"|revela|revelame|revelar|revelarme|imprime|imprimi|decime|dime"
    r"|copi(?:a|ame|ar|arme)|compart(?:e|ime|ir|irme))\s+"
    r"(?:(?:aca|aqui)\s+)?(?:(?:la|las|el|una|tu|tus|mi)\s+)?"
    r"(?:clave\s+(?:de\s+)?api|prompt\s+(?:de|del)\s+sistema"
    r"|instrucciones\s+(?:internas|(?:de|del)\s+sistema))"
    r"|(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
    r"(?:show|reveal|print|give|copy|share)\s+(?:me\s+)?"
    r"(?:(?:the|a|your|my)\s+)?(?:api[\s_-]+key|system[\s_-]+prompt|internal\s+instructions)"
    r")\b"
)


def check_query(query: str) -> None:
    normalized = unicodedata.normalize("NFKD", query.casefold())
    plain_text = "".join(char for char in normalized if not unicodedata.combining(char))
    if _OVERRIDE_INSTRUCTIONS.search(plain_text) or _DISCLOSE_PROTECTED_TEXT.search(plain_text):
        raise BlockedQueryError("Consulta bloqueada por el filtro de entrada.")
