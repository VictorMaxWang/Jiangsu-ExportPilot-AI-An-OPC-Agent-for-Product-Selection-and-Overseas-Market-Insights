from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Literal

from app.core.config import Settings, get_settings
from app.schemas.provider_status import (
    ProviderCapabilityStatus,
    ProviderId,
    ProviderMvpPriority,
    ProviderStatusItem,
    ProviderStatusResponse,
    ProviderTestResponse,
)
from app.services.ai import BailianClient, BailianError
from app.services.providers.etsy import ETSY_LISTINGS_REQUIRES_OAUTH_OR_APPROVAL, EtsyProvider
from app.services.providers.gdelt import GdeltProvider
from app.services.providers.un_comtrade import UnComtradeProvider
from app.services.providers.worldbank import WorldBankProvider
from app.services.providers.youtube import YoutubeProvider


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"


@dataclass(frozen=True)
class ProviderDefinition:
    provider: ProviderId
    display_name: str
    mvp_priority: ProviderMvpPriority
    fallback: str | None
    notes: str


PROVIDER_DEFINITIONS: tuple[ProviderDefinition, ...] = (
    ProviderDefinition(
        provider="bailian",
        display_name="Alibaba Cloud Bailian qwen3.6-plus",
        mvp_priority="P0",
        fallback="mock/sample AI text",
        notes="Server-side model access status only.",
    ),
    ProviderDefinition(
        provider="worldbank",
        display_name="World Bank Indicators API",
        mvp_priority="P0",
        fallback="data/seed/market_profiles.csv",
        notes="Public no-credential API.",
    ),
    ProviderDefinition(
        provider="gdelt",
        display_name="GDELT DOC API",
        mvp_priority="P0",
        fallback="data/seed/content_trends.csv",
        notes="Public no-credential API.",
    ),
    ProviderDefinition(
        provider="youtube",
        display_name="YouTube Data API v3",
        mvp_priority="P0",
        fallback="data/seed/content_trends.csv",
        notes="Server-side configuration status only.",
    ),
    ProviderDefinition(
        provider="etsy",
        display_name="Etsy Open API",
        mvp_priority="P0",
        fallback="data/seed/competitor_samples.csv",
        notes="Server-side configuration status only.",
    ),
    ProviderDefinition(
        provider="un_comtrade",
        display_name="UN Comtrade",
        mvp_priority="P1",
        fallback="data/seed/trade_samples.csv",
        notes="No-credential-first mode with optional server-side configuration.",
    ),
    ProviderDefinition(
        provider="csv_fallback",
        display_name="CSV fallback",
        mvp_priority="P0",
        fallback="data/seed/*.csv",
        notes="Local sample data for demo continuity.",
    ),
    ProviderDefinition(
        provider="ebay",
        display_name="eBay Browse API",
        mvp_priority="P2",
        fallback=None,
        notes="Manual registration pending; live calls are not attempted.",
    ),
    ProviderDefinition(
        provider="rakuten",
        display_name="Rakuten Ichiba API",
        mvp_priority="P2",
        fallback=None,
        notes="Manual registration pending; live calls are not attempted.",
    ),
    ProviderDefinition(
        provider="reddit",
        display_name="Reddit API",
        mvp_priority="P2",
        fallback=None,
        notes="Manual registration pending; live calls are not attempted.",
    ),
)

PROVIDER_BY_ID = {definition.provider: definition for definition in PROVIDER_DEFINITIONS}

REQUIRED_SEED_FILES: tuple[str, ...] = (
    "competitor_samples.csv",
    "content_trends.csv",
    "market_profiles.csv",
    "product_catalog.csv",
    "trade_samples.csv",
    "user_discussions.csv",
)


class ProviderStatusService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        bailian_client: BailianClient | None = None,
        worldbank_provider: WorldBankProvider | None = None,
        gdelt_provider: GdeltProvider | None = None,
        youtube_provider: YoutubeProvider | None = None,
        etsy_provider: EtsyProvider | None = None,
        un_comtrade_provider: UnComtradeProvider | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR
        self._bailian_client = bailian_client or BailianClient(self._settings)
        self._worldbank_provider = worldbank_provider or WorldBankProvider(seed_dir=self._seed_dir)
        self._gdelt_provider = gdelt_provider or GdeltProvider(seed_dir=self._seed_dir)
        self._youtube_provider = youtube_provider or YoutubeProvider(settings=self._settings, seed_dir=self._seed_dir)
        self._etsy_provider = etsy_provider or EtsyProvider(settings=self._settings, seed_dir=self._seed_dir)
        self._un_comtrade_provider = un_comtrade_provider or UnComtradeProvider(
            settings=self._settings,
            seed_dir=self._seed_dir,
        )

    def list_status(self) -> ProviderStatusResponse:
        return ProviderStatusResponse(
            providers=[
                ProviderStatusItem(
                    provider=definition.provider,
                    display_name=definition.display_name,
                    status=self._status_for(definition.provider),
                    mvp_priority=definition.mvp_priority,
                    default_enabled=self._default_enabled_for(definition.provider),
                    fallback=definition.fallback,
                    notes=definition.notes,
                )
                for definition in PROVIDER_DEFINITIONS
            ]
        )

    async def test_provider(self, provider: ProviderId, *, force_live: bool = False) -> ProviderTestResponse:
        start = perf_counter()
        checked_at = datetime.now(timezone.utc)
        try:
            if provider == "bailian":
                return self._with_timing(await self._test_bailian(checked_at), start)
            if provider == "worldbank":
                return self._with_timing(await self._test_worldbank(checked_at), start)
            if provider == "gdelt":
                return self._with_timing(await self._test_gdelt(checked_at), start)
            if provider == "youtube":
                return self._with_timing(await self._test_youtube(checked_at, force_live=force_live), start)
            if provider == "etsy":
                return self._with_timing(await self._test_etsy(checked_at, force_live=force_live), start)
            if provider == "un_comtrade":
                return self._with_timing(await self._test_un_comtrade(checked_at, force_live=force_live), start)
            if provider == "csv_fallback":
                return self._with_timing(self._test_csv_fallback(checked_at), start)
            return self._with_timing(self._pending_response(provider, checked_at), start)
        except Exception:
            return self._with_timing(
                ProviderTestResponse(
                    provider=provider,
                    status="unavailable",
                    checked_at=checked_at,
                    latency_ms=0,
                    fallback_used=False,
                    message="Provider test failed with a sanitized internal error.",
                    sample_count=0,
                    error_code="PROVIDER_TEST_FAILED",
                    configured=self._is_configured_for(provider),
                    fallback_available=self._fallback_available(provider),
                    cache_bypassed=force_live,
                ),
                start,
            )

    def _status_for(self, provider: ProviderId) -> ProviderCapabilityStatus:
        if provider == "bailian":
            return "configured" if self._settings.bailian_api_key else "not_configured"
        if provider in {"worldbank", "gdelt", "csv_fallback"}:
            return "active_no_key"
        if provider == "youtube":
            if not self._settings.enable_youtube:
                return "disabled"
            return "configured" if self._settings.youtube_data_api_key else "not_configured"
        if provider == "etsy":
            if not self._settings.enable_etsy:
                return "disabled"
            return "configured" if self._settings.etsy_keystring and self._settings.etsy_shared_secret else "not_configured"
        if provider == "un_comtrade":
            return "optional_no_key_first" if self._settings.enable_un_comtrade else "disabled"
        if provider in {"ebay", "rakuten", "reddit"}:
            return "pending_manual_registration"
        return "unavailable"

    def _default_enabled_for(self, provider: ProviderId) -> bool:
        if provider == "bailian":
            return bool(self._settings.bailian_api_key)
        if provider in {"worldbank", "gdelt", "csv_fallback"}:
            return True
        if provider == "youtube":
            return self._settings.enable_youtube
        if provider == "etsy":
            return self._settings.enable_etsy
        if provider == "un_comtrade":
            return self._settings.enable_un_comtrade
        return False

    async def _test_bailian(self, checked_at: datetime) -> ProviderTestResponse:
        if not self._settings.bailian_api_key:
            return ProviderTestResponse(
                provider="bailian",
                status="pending",
                checked_at=checked_at,
                latency_ms=0,
                fallback_used=False,
                message="Server configuration is not set.",
                sample_count=0,
                error_code="BAILIAN_NOT_CONFIGURED",
                configured=False,
            )

        try:
            result = await self._bailian_client.chat(
                [{"role": "user", "content": "Reply with OK."}],
                temperature=0.0,
                max_tokens=16,
            )
        except BailianError as exc:
            return ProviderTestResponse(
                provider="bailian",
                status="unavailable",
                checked_at=checked_at,
                latency_ms=0,
                fallback_used=False,
                message="Bailian test failed.",
                sample_count=0,
                error_code=exc.code,
                configured=True,
            )

        sample_count = 1 if result.content.strip() else 0
        return ProviderTestResponse(
            provider="bailian",
            status="success" if sample_count else "unavailable",
            checked_at=checked_at,
            latency_ms=0,
            fallback_used=False,
            message="Bailian returned a valid response." if sample_count else "Bailian returned an empty response.",
            sample_count=sample_count,
            error_code=None if sample_count else "EMPTY_PROVIDER_RESPONSE",
            configured=True,
        )

    async def _test_worldbank(self, checked_at: datetime) -> ProviderTestResponse:
        payload = await self._worldbank_provider.fetch_country("US")
        sample_count = len(payload.indicators)
        return self._provider_payload_response(
            provider="worldbank",
            checked_at=checked_at,
            sample_count=sample_count,
            fallback_used=payload.fallback_used,
        )

    async def _test_gdelt(self, checked_at: datetime) -> ProviderTestResponse:
        payload = await self._gdelt_provider.search("home textile", max_records=1)
        sample_count = len(payload.items)
        return self._provider_payload_response(
            provider="gdelt",
            checked_at=checked_at,
            sample_count=sample_count,
            fallback_used=payload.fallback_used,
        )

    async def _test_youtube(self, checked_at: datetime, *, force_live: bool = False) -> ProviderTestResponse:
        configured = self._is_configured_for("youtube")
        fallback_available = self._fallback_available("youtube")
        if force_live and not configured:
            return ProviderTestResponse(
                provider="youtube",
                status="pending",
                checked_at=checked_at,
                latency_ms=0,
                fallback_used=False,
                message="Server configuration is not set.",
                sample_count=0,
                error_code="YOUTUBE_NOT_CONFIGURED",
                configured=False,
                live_ping_success=None,
                live_search_success=False,
                fallback_available=fallback_available,
                cache_bypassed=True,
            )

        try:
            payload = await self._youtube_provider.search_videos(
                "home decor",
                country="US",
                max_results=1,
                allow_fallback=not force_live,
            )
        except Exception:
            fallback_count = self._fallback_sample_count("youtube", limit=1)
            return ProviderTestResponse(
                provider="youtube",
                status="fallback" if fallback_available else "unavailable",
                checked_at=checked_at,
                latency_ms=0,
                fallback_used=fallback_available,
                message=(
                    "YouTube live search failed; CSV fallback is available."
                    if fallback_available
                    else "YouTube live search failed."
                ),
                sample_count=fallback_count,
                error_code="YOUTUBE_LIVE_SEARCH_FAILED",
                configured=configured,
                live_ping_success=None,
                live_search_success=False,
                fallback_available=fallback_available,
                cache_bypassed=force_live,
            )

        sample_count = len(payload.items)
        return self._provider_payload_response(
            provider="youtube",
            checked_at=checked_at,
            sample_count=sample_count,
            fallback_used=payload.fallback_used,
            configured=configured,
            fallback_available=fallback_available or payload.fallback_used,
            cache_bypassed=force_live,
            live_search_success=(sample_count > 0 and not payload.fallback_used) if force_live else None,
        )

    async def _test_etsy(self, checked_at: datetime, *, force_live: bool = False) -> ProviderTestResponse:
        configured = self._is_configured_for("etsy")
        fallback_available = self._fallback_available("etsy")
        if force_live and not configured:
            return ProviderTestResponse(
                provider="etsy",
                status="pending",
                checked_at=checked_at,
                latency_ms=0,
                fallback_used=False,
                message="Server configuration is not set.",
                sample_count=0,
                error_code="ETSY_NOT_CONFIGURED",
                configured=False,
                live_ping_success=False,
                live_search_success=False,
                fallback_available=fallback_available,
                cache_bypassed=True,
            )

        if force_live:
            try:
                await self._etsy_provider.openapi_ping()
            except Exception:
                fallback_count = self._fallback_sample_count("etsy", limit=1)
                return ProviderTestResponse(
                    provider="etsy",
                    status="fallback" if fallback_available else "unavailable",
                    checked_at=checked_at,
                    latency_ms=0,
                    fallback_used=fallback_available,
                    message=(
                        "Etsy credentials could not be validated; CSV fallback is available."
                        if fallback_available
                        else "Etsy credentials could not be validated."
                    ),
                    sample_count=fallback_count,
                    error_code="ETSY_PING_FAILED",
                    configured=configured,
                    live_ping_success=False,
                    live_search_success=False,
                    fallback_available=fallback_available,
                    cache_bypassed=True,
                )

            try:
                payload = await self._etsy_provider.search_listings(
                    "home decor",
                    country="US",
                    limit=1,
                    allow_fallback=False,
                )
            except Exception as exc:
                fallback_count = self._fallback_sample_count("etsy", limit=1)
                error_code = str(getattr(exc, "code", "ETSY_LIVE_SEARCH_FAILED"))
                if error_code == ETSY_LISTINGS_REQUIRES_OAUTH_OR_APPROVAL:
                    return ProviderTestResponse(
                        provider="etsy",
                        status="credentials_valid_but_listing_search_requires_oauth_or_approval",
                        checked_at=checked_at,
                        latency_ms=0,
                        fallback_used=fallback_available,
                        message="Etsy credentials are valid, but listing search requires OAuth, approval, or additional access.",
                        sample_count=fallback_count,
                        error_code=ETSY_LISTINGS_REQUIRES_OAUTH_OR_APPROVAL,
                        configured=True,
                        live_ping_success=True,
                        live_search_success=False,
                        fallback_available=fallback_available,
                        cache_bypassed=True,
                    )
                return ProviderTestResponse(
                    provider="etsy",
                    status="fallback" if fallback_available else "unavailable",
                    checked_at=checked_at,
                    latency_ms=0,
                    fallback_used=fallback_available,
                    message=(
                        "Etsy live listing search failed; CSV fallback is available."
                        if fallback_available
                        else "Etsy live listing search failed."
                    ),
                    sample_count=fallback_count,
                    error_code="ETSY_LIVE_SEARCH_FAILED",
                    configured=configured,
                    live_ping_success=True,
                    live_search_success=False,
                    fallback_available=fallback_available,
                    cache_bypassed=True,
                )
        else:
            payload = await self._etsy_provider.search_listings("boho blanket", country="US", limit=1)

        sample_count = len(payload.items)
        return self._provider_payload_response(
            provider="etsy",
            checked_at=checked_at,
            sample_count=sample_count,
            fallback_used=payload.fallback_used,
            configured=configured,
            fallback_available=fallback_available or payload.fallback_used,
            cache_bypassed=force_live,
            live_ping_success=True if force_live else None,
            live_search_success=(sample_count > 0 and not payload.fallback_used) if force_live else None,
        )

    async def _test_un_comtrade(self, checked_at: datetime, *, force_live: bool = False) -> ProviderTestResponse:
        payload = await self._un_comtrade_provider.get_trade_flow(
            reporter="CHN",
            partner="USA",
            hs_code="6302",
            flow="export",
            start_year=2024,
            end_year=2024,
        )
        sample_count = len(payload.records)
        return self._provider_payload_response(
            provider="un_comtrade",
            checked_at=checked_at,
            sample_count=sample_count,
            fallback_used=payload.fallback_used,
            configured=self._is_configured_for("un_comtrade"),
            fallback_available=self._fallback_available("un_comtrade") or payload.fallback_used,
            cache_bypassed=force_live,
            live_search_success=(sample_count > 0 and not payload.fallback_used) if force_live else None,
            auth_mode=payload.auth_mode,
        )

    def _test_csv_fallback(self, checked_at: datetime) -> ProviderTestResponse:
        total_rows = 0
        for filename in REQUIRED_SEED_FILES:
            row_count = _readable_csv_row_count(self._seed_dir / filename)
            if row_count is None or row_count == 0:
                return ProviderTestResponse(
                    provider="csv_fallback",
                    status="unavailable",
                    checked_at=checked_at,
                    latency_ms=0,
                    fallback_used=False,
                    message="One or more seed files are missing or empty.",
                    sample_count=total_rows,
                    error_code="CSV_SEED_UNAVAILABLE",
                    configured=True,
                )
            total_rows += row_count

        return ProviderTestResponse(
            provider="csv_fallback",
            status="success",
            checked_at=checked_at,
            latency_ms=0,
            fallback_used=False,
            message="Seed files are readable.",
            sample_count=total_rows,
            error_code=None,
            configured=True,
            fallback_available=True,
        )

    def _provider_payload_response(
        self,
        *,
        provider: ProviderId,
        checked_at: datetime,
        sample_count: int,
        fallback_used: bool,
        configured: bool | None = None,
        fallback_available: bool | None = None,
        cache_bypassed: bool = False,
        live_ping_success: bool | None = None,
        live_search_success: bool | None = None,
        auth_mode: Literal["no_key", "key", "fallback"] | None = None,
    ) -> ProviderTestResponse:
        provider_configured = self._is_configured_for(provider) if configured is None else configured
        provider_fallback_available = self._fallback_available(provider) if fallback_available is None else fallback_available
        if sample_count == 0:
            return ProviderTestResponse(
                provider=provider,
                status="unavailable",
                checked_at=checked_at,
                latency_ms=0,
                fallback_used=fallback_used,
                message="Provider returned no usable sample rows.",
                sample_count=0,
                error_code="EMPTY_PROVIDER_RESPONSE",
                configured=provider_configured,
                live_ping_success=live_ping_success,
                live_search_success=False if cache_bypassed else live_search_success,
                fallback_available=provider_fallback_available,
                cache_bypassed=cache_bypassed,
                auth_mode=auth_mode,
            )

        status: Literal["success", "fallback"] = "fallback" if fallback_used else "success"
        message = "Fallback sample data is available." if fallback_used else "Provider returned usable sample data."
        return ProviderTestResponse(
            provider=provider,
            status=status,
            checked_at=checked_at,
            latency_ms=0,
            fallback_used=fallback_used,
            message=message,
            sample_count=sample_count,
            error_code=None,
            configured=provider_configured,
            live_ping_success=live_ping_success,
            live_search_success=live_search_success,
            fallback_available=provider_fallback_available,
            cache_bypassed=cache_bypassed,
            auth_mode=auth_mode,
        )

    def _pending_response(self, provider: ProviderId, checked_at: datetime) -> ProviderTestResponse:
        return ProviderTestResponse(
            provider=provider,
            status="pending",
            checked_at=checked_at,
            latency_ms=0,
            fallback_used=False,
            message="Manual provider registration is pending; no live call was attempted.",
            sample_count=0,
            error_code="PROVIDER_PENDING_MANUAL_REGISTRATION",
            configured=self._is_configured_for(provider),
            fallback_available=self._fallback_available(provider),
        )

    def _with_timing(self, response: ProviderTestResponse, start: float) -> ProviderTestResponse:
        response.latency_ms = max(0, round((perf_counter() - start) * 1000))
        return response

    def _is_configured_for(self, provider: ProviderId) -> bool:
        if provider == "bailian":
            return bool(self._settings.bailian_api_key)
        if provider in {"worldbank", "gdelt", "csv_fallback"}:
            return True
        if provider == "youtube":
            return bool(self._settings.enable_youtube and self._settings.youtube_data_api_key)
        if provider == "etsy":
            return bool(self._settings.enable_etsy and self._settings.etsy_keystring and self._settings.etsy_shared_secret)
        if provider == "un_comtrade":
            return self._settings.enable_un_comtrade
        return False

    def _fallback_available(self, provider: ProviderId) -> bool:
        return self._fallback_sample_count(provider, limit=1) > 0

    def _fallback_sample_count(self, provider: ProviderId, *, limit: int) -> int:
        files_by_provider: dict[ProviderId, tuple[str, ...]] = {
            "bailian": (),
            "worldbank": ("market_profiles.csv",),
            "gdelt": ("content_trends.csv",),
            "youtube": ("content_trends.csv",),
            "etsy": ("competitor_samples.csv",),
            "un_comtrade": ("trade_samples.csv",),
            "csv_fallback": REQUIRED_SEED_FILES,
            "ebay": (),
            "rakuten": (),
            "reddit": (),
        }
        total = 0
        for filename in files_by_provider.get(provider, ()):
            row_count = _readable_csv_row_count(self._seed_dir / filename) or 0
            total += row_count
            if total >= limit:
                return limit
        return total


def get_provider_status_service() -> ProviderStatusService:
    return ProviderStatusService()


def _readable_csv_row_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if not reader.fieldnames:
                return None
            return sum(1 for row in reader if any(value for value in row.values()))
    except (OSError, csv.Error, UnicodeDecodeError):
        return None
