from src.llm.config import LLMConfig, normalize_provider
from src.llm.errors import LLMConfigurationError
from src.llm.providers.base import LLMProvider
from src.llm.providers.gemini_provider import GeminiProvider
from src.llm.providers.openai_provider import OpenAIProvider


def build_provider(config: LLMConfig) -> LLMProvider:
    provider = normalize_provider(config.provider)
    if provider == "openai":
        return OpenAIProvider(config)
    if provider == "gemini":
        return GeminiProvider(config)
    raise LLMConfigurationError(f"No hay un adaptador implementado para {provider}.")
