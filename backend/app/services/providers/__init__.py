"""Public data provider clients."""


class DataProviderValidationError(ValueError):
    """Raised when a provider receives unsupported user input."""


API_SOURCE = "api"
CSV_FALLBACK_SOURCE = "csv_fallback"
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 7.0
DEFAULT_PROVIDER_CONNECT_TIMEOUT_SECONDS = 3.0


__all__ = [
    "API_SOURCE",
    "CSV_FALLBACK_SOURCE",
    "DEFAULT_PROVIDER_CONNECT_TIMEOUT_SECONDS",
    "DEFAULT_PROVIDER_TIMEOUT_SECONDS",
    "DataProviderValidationError",
]
