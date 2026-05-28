"""Public data provider clients."""


class DataProviderValidationError(ValueError):
    """Raised when a provider receives unsupported user input."""


API_SOURCE = "api"
CSV_FALLBACK_SOURCE = "csv_fallback"


__all__ = ["API_SOURCE", "CSV_FALLBACK_SOURCE", "DataProviderValidationError"]
