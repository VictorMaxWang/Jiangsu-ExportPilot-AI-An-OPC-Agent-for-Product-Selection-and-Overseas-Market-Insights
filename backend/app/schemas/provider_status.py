from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ProviderId = Literal[
    "bailian",
    "worldbank",
    "gdelt",
    "youtube",
    "etsy",
    "un_comtrade",
    "csv_fallback",
    "ebay",
    "rakuten",
    "reddit",
]

ProviderCapabilityStatus = Literal[
    "active_no_key",
    "configured",
    "not_configured",
    "optional_no_key_first",
    "pending_manual_registration",
    "fallback_only",
    "disabled",
    "unavailable",
]

ProviderMvpPriority = Literal["P0", "P1", "P2"]
ProviderTestStatus = Literal[
    "success",
    "fallback",
    "pending",
    "unavailable",
    "credentials_valid_but_listing_search_requires_oauth_or_approval",
]
ProviderTestAuthMode = Literal["no_key", "key", "fallback"]


class ProviderStatusItem(BaseModel):
    provider: ProviderId
    display_name: str
    status: ProviderCapabilityStatus
    mvp_priority: ProviderMvpPriority
    default_enabled: bool
    fallback: str | None = None
    notes: str


class ProviderStatusResponse(BaseModel):
    providers: list[ProviderStatusItem]


class ProviderTestResponse(BaseModel):
    provider: ProviderId
    status: ProviderTestStatus
    checked_at: datetime
    latency_ms: int
    fallback_used: bool
    message: str
    sample_count: int
    error_code: str | None = None
    configured: bool = False
    live_ping_success: bool | None = None
    live_search_success: bool | None = None
    fallback_available: bool = False
    cache_bypassed: bool = False
    auth_mode: ProviderTestAuthMode | None = None
