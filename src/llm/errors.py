class LLMConfigurationError(ValueError):
    """Configuration is missing or invalid before an API request is sent."""


class ProviderCallError(RuntimeError):
    """Provider error normalized across SDKs without retaining prompt data."""

    def __init__(
        self,
        provider: str,
        kind: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.kind = kind
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class InvalidStructuredResponse(ValueError):
    """The provider response could not be validated against the app contract."""

    def __init__(self, message: str, issues: list[dict[str, str]] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []
