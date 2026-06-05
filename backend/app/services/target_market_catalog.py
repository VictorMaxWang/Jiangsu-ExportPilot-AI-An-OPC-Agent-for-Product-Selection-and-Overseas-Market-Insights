from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.countries import normalize_country_codes
from app.models import AnalysisCountryPreset, TargetCountry
from app.schemas import (
    AnalysisCountryPresetCatalogItem,
    AnalysisCountryPresetCatalogResponse,
    AnalysisCountryPresetCreate,
    TargetCountryCatalogItem,
    TargetCountryCatalogResponse,
    TargetCountryCreate,
)
from app.schemas.target_markets import CatalogSource


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"


class TargetMarketCatalogError(ValueError):
    pass


class TargetMarketCatalogService:
    def __init__(self, db: Session, *, seed_dir: Path | None = None) -> None:
        self._db = db
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    def list_countries(
        self,
        *,
        region_code: str | None = None,
        continent: str | None = None,
        include_disabled: bool = False,
        analysis_only: bool = True,
    ) -> TargetCountryCatalogResponse:
        source = self._country_source()
        if source == "database":
            statement = select(TargetCountry)
            if region_code:
                statement = statement.where(TargetCountry.region_code == region_code.strip().upper())
            if continent:
                statement = statement.where(TargetCountry.continent == continent.strip())
            if not include_disabled:
                statement = statement.where(TargetCountry.enabled.is_(True))
            if analysis_only:
                statement = statement.where(TargetCountry.analysis_enabled.is_(True))
            statement = statement.order_by(TargetCountry.default_sort_order, TargetCountry.country_code)
            items = [
                TargetCountryCatalogItem.model_validate(row).model_copy(update={"source": source})
                for row in self._db.scalars(statement)
            ]
        else:
            items = [
                item
                for item in self._seed_country_items()
                if _country_filter_matches(
                    item,
                    region_code=region_code,
                    continent=continent,
                    include_disabled=include_disabled,
                    analysis_only=analysis_only,
                )
            ]
            items.sort(key=lambda item: (item.default_sort_order, item.country_code))
        return TargetCountryCatalogResponse(items=items, total=len(items), source=source)

    def list_presets(
        self,
        *,
        region_code: str | None = None,
        default_only: bool = False,
        include_disabled: bool = False,
    ) -> AnalysisCountryPresetCatalogResponse:
        source = self._preset_source()
        if source == "database":
            statement = select(AnalysisCountryPreset)
            if region_code:
                statement = statement.where(AnalysisCountryPreset.region_code == region_code.strip().upper())
            if default_only:
                statement = statement.where(AnalysisCountryPreset.is_default.is_(True))
            if not include_disabled:
                statement = statement.where(AnalysisCountryPreset.enabled.is_(True))
            statement = statement.order_by(AnalysisCountryPreset.sort_order, AnalysisCountryPreset.preset_code)
            items = [
                AnalysisCountryPresetCatalogItem.model_validate(row).model_copy(update={"source": source})
                for row in self._db.scalars(statement)
            ]
        else:
            items = [
                item
                for item in self._seed_preset_items()
                if _preset_filter_matches(
                    item,
                    region_code=region_code,
                    default_only=default_only,
                    include_disabled=include_disabled,
                )
            ]
            items.sort(key=lambda item: (item.sort_order, item.preset_code))
        return AnalysisCountryPresetCatalogResponse(items=items, total=len(items), source=source)

    def validate_analysis_countries(self, country_codes: list[str]) -> list[str]:
        try:
            normalized = normalize_country_codes(country_codes, field_name="target_countries")
        except ValueError as exc:
            raise TargetMarketCatalogError(str(exc)) from exc
        country_map = {item.country_code: item for item in self._analysis_validation_items()}
        missing: list[str] = []
        disabled: list[str] = []
        not_analysis_enabled: list[str] = []
        for code in normalized:
            item = country_map.get(code)
            if item is None:
                missing.append(code)
            elif not item.enabled:
                disabled.append(code)
            elif not item.analysis_enabled:
                not_analysis_enabled.append(code)
        if missing or disabled or not_analysis_enabled:
            parts: list[str] = []
            if missing:
                parts.append(f"unsupported countries: {', '.join(missing)}")
            if disabled:
                parts.append(f"disabled countries: {', '.join(disabled)}")
            if not_analysis_enabled:
                parts.append(f"countries not enabled for analysis: {', '.join(not_analysis_enabled)}")
            raise TargetMarketCatalogError("; ".join(parts))
        return normalized

    def _analysis_validation_items(self) -> list[TargetCountryCatalogItem]:
        if self._country_source() == "database":
            return [
                TargetCountryCatalogItem.model_validate(row).model_copy(update={"source": "database"})
                for row in self._db.scalars(select(TargetCountry).order_by(TargetCountry.default_sort_order))
            ]
        return self._seed_country_items()

    def _country_source(self) -> CatalogSource:
        return "database" if self._db.scalar(select(func.count()).select_from(TargetCountry)) else "csv_fallback"

    def _preset_source(self) -> CatalogSource:
        return "database" if self._db.scalar(select(func.count()).select_from(AnalysisCountryPreset)) else "csv_fallback"

    def _seed_country_items(self) -> list[TargetCountryCatalogItem]:
        items: list[TargetCountryCatalogItem] = []
        for row in _read_csv_rows(self._seed_dir / "target_countries.csv"):
            payload = dict(row)
            payload["languages"] = _list_from_text(payload.get("languages"))
            payload["default_sort_order"] = _int_from_text(payload.get("default_sort_order"), default=0)
            payload["enabled"] = _bool_from_text(payload.get("enabled"), default=True)
            payload["analysis_enabled"] = _bool_from_text(payload.get("analysis_enabled"), default=True)
            payload["fallback_enabled"] = _bool_from_text(payload.get("fallback_enabled"), default=True)
            payload["provider_mappings"] = _json_from_text(payload.get("provider_mappings"))
            created = TargetCountryCreate(**payload)
            items.append(TargetCountryCatalogItem(**created.model_dump(), source="csv_fallback"))
        return items

    def _seed_preset_items(self) -> list[AnalysisCountryPresetCatalogItem]:
        items: list[AnalysisCountryPresetCatalogItem] = []
        for row in _read_csv_rows(self._seed_dir / "analysis_country_presets.csv"):
            payload = dict(row)
            payload["country_codes"] = _list_from_text(payload.get("country_codes"))
            payload["industry_tags"] = _list_from_text(payload.get("industry_tags"))
            payload["is_default"] = _bool_from_text(payload.get("is_default"), default=False)
            payload["sort_order"] = _int_from_text(payload.get("sort_order"), default=0)
            payload["enabled"] = _bool_from_text(payload.get("enabled"), default=True)
            created = AnalysisCountryPresetCreate(**payload)
            items.append(AnalysisCountryPresetCatalogItem(**created.model_dump(), source="csv_fallback"))
        return items


def _country_filter_matches(
    item: TargetCountryCatalogItem,
    *,
    region_code: str | None,
    continent: str | None,
    include_disabled: bool,
    analysis_only: bool,
) -> bool:
    if region_code and item.region_code != region_code.strip().upper():
        return False
    if continent and item.continent != continent.strip():
        return False
    if not include_disabled and not item.enabled:
        return False
    if analysis_only and not item.analysis_enabled:
        return False
    return True


def _preset_filter_matches(
    item: AnalysisCountryPresetCatalogItem,
    *,
    region_code: str | None,
    default_only: bool,
    include_disabled: bool,
) -> bool:
    if region_code and item.region_code != region_code.strip().upper():
        return False
    if default_only and not item.is_default:
        return False
    if not include_disabled and not item.enabled:
        return False
    return True


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return [_clean_row(row) for row in csv.DictReader(csv_file) if not _blank_row(row)]
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _blank_row(row: dict[str, str | None]) -> bool:
    return all(value is None or value == "" for key, value in row.items() if key is not None)


def _list_from_text(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in value.replace("|", ";").split(";") if part.strip()]


def _json_from_text(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("provider_mappings must be a JSON object")
    return parsed


def _bool_from_text(value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _int_from_text(value: str | None, *, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value.strip())
