from __future__ import annotations

import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Company,
    CompetitorItem,
    ContentTrend,
    MarketIndicator,
    Product,
    ProductKeyword,
    TradeStat,
)
from app.schemas.imports import CsvImportErrorDetail, CsvImportResult, ImportMode


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
CSV_SOURCE = "csv_fallback"


class CsvImportRequestError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class CsvImportValidationError(Exception):
    def __init__(self, result: CsvImportResult) -> None:
        self.result = result
        super().__init__("CSV import validation failed")


def import_products(
    db: Session,
    *,
    file_name: str | None = None,
    mode: ImportMode = "insert",
    company_id: int | None = None,
    seed_dir: Path | None = None,
) -> CsvImportResult:
    dataset = "products"
    default_file_name = "product_catalog.csv"
    if company_id is None:
        result = _empty_result(dataset, file_name or default_file_name, mode)
        result.errors.append(
            CsvImportErrorDetail(
                row_number=1,
                field="company_id",
                message="company_id is required for product imports",
            )
        )
        result.failed = 1
        raise CsvImportValidationError(result)
    if db.get(Company, company_id) is None:
        raise CsvImportRequestError(f"Company {company_id} not found", status_code=404)

    loaded = _load_csv(
        dataset,
        default_file_name,
        mode,
        required_headers={
            "product_key",
            "product_name_cn",
            "product_name_en",
            "category",
            "cost_price_cny",
            "weight_kg",
            "package_size",
            "material",
            "certification",
            "moq",
            "keywords",
            "description",
        },
        file_name=file_name,
        seed_dir=seed_dir,
    )

    products: list[tuple[Product, list[str]]] = []
    for row_number, row in loaded.rows:
        product_name_cn = _required_text(row, row_number, "product_name_cn", loaded.result.errors)
        product = Product(
            company_id=company_id,
            product_name_cn=product_name_cn,
            product_name_en=_optional_text(row, "product_name_en"),
            category=_optional_text(row, "category"),
            cost_price_cny=_optional_decimal(row, row_number, "cost_price_cny", loaded.result.errors),
            weight_kg=_optional_decimal(row, row_number, "weight_kg", loaded.result.errors),
            package_size=_optional_text(row, "package_size"),
            material=_optional_text(row, "material"),
            certification=_optional_text(row, "certification"),
            moq=_optional_int(row, row_number, "moq", loaded.result.errors),
            description=_optional_text(row, "description"),
        )
        products.append((product, _split_keywords(row.get("keywords"))))

    _raise_if_errors(loaded.result)
    if mode == "validate":
        loaded.result.valid_rows = loaded.result.total_rows
        return loaded.result

    try:
        for product, keywords in products:
            db.add(product)
            db.flush()
            for keyword in keywords:
                db.add(
                    ProductKeyword(
                        product_id=product.id,
                        keyword=keyword,
                        language="en",
                        source=CSV_SOURCE,
                    )
                )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise CsvImportRequestError("Database insert failed during product import", 500) from exc

    loaded.result.valid_rows = loaded.result.total_rows
    loaded.result.inserted = len(products)
    return loaded.result


def import_competitors(
    db: Session,
    *,
    file_name: str | None = None,
    mode: ImportMode = "insert",
    seed_dir: Path | None = None,
) -> CsvImportResult:
    loaded = _load_csv(
        "competitors",
        "competitor_samples.csv",
        mode,
        required_headers={
            "platform",
            "country",
            "keyword",
            "title",
            "price",
            "currency",
            "rating",
            "review_count",
            "product_url",
            "image_url",
            "collected_at",
        },
        file_name=file_name,
        seed_dir=seed_dir,
    )

    items: list[CompetitorItem] = []
    for row_number, row in loaded.rows:
        items.append(
            CompetitorItem(
                platform=_required_text(row, row_number, "platform", loaded.result.errors),
                country=_required_text(row, row_number, "country", loaded.result.errors),
                keyword=_required_text(row, row_number, "keyword", loaded.result.errors),
                title=_required_text(row, row_number, "title", loaded.result.errors),
                price=_optional_decimal(row, row_number, "price", loaded.result.errors),
                currency=_optional_text(row, "currency"),
                rating=_optional_decimal(row, row_number, "rating", loaded.result.errors),
                review_count=_optional_int(row, row_number, "review_count", loaded.result.errors),
                product_url=_optional_text(row, "product_url"),
                image_url=_optional_text(row, "image_url"),
                source_type=CSV_SOURCE,
                collected_at=_optional_datetime(row, row_number, "collected_at", loaded.result.errors),
            )
        )

    return _insert_objects(db, loaded.result, items, mode)


def import_market_profiles(
    db: Session,
    *,
    file_name: str | None = None,
    mode: ImportMode = "insert",
    seed_dir: Path | None = None,
) -> CsvImportResult:
    loaded = _load_csv(
        "market-profiles",
        "market_profiles.csv",
        mode,
        required_headers={
            "country_code",
            "country_name",
            "gdp_per_capita",
            "population",
            "internet_penetration",
            "market_size_level",
            "competition_level",
            "logistics_difficulty",
            "notes",
        },
        file_name=file_name,
        seed_dir=seed_dir,
    )

    indicators: list[MarketIndicator] = []
    for row_number, row in loaded.rows:
        country_code = _required_text(row, row_number, "country_code", loaded.result.errors)
        country_name = _required_text(row, row_number, "country_name", loaded.result.errors)
        indicators.extend(
            [
                _market_indicator(
                    country_code,
                    country_name,
                    "GDP_PER_CAPITA",
                    "GDP per capita",
                    _optional_decimal(row, row_number, "gdp_per_capita", loaded.result.errors),
                ),
                _market_indicator(
                    country_code,
                    country_name,
                    "POPULATION",
                    "Population",
                    _optional_decimal(row, row_number, "population", loaded.result.errors),
                ),
                _market_indicator(
                    country_code,
                    country_name,
                    "INTERNET_PENETRATION",
                    "Internet penetration",
                    _optional_decimal(row, row_number, "internet_penetration", loaded.result.errors),
                ),
                _market_indicator(
                    country_code,
                    country_name,
                    "MARKET_SIZE_LEVEL",
                    "Market size level",
                    _level_decimal(row, row_number, "market_size_level", loaded.result.errors),
                ),
                _market_indicator(
                    country_code,
                    country_name,
                    "COMPETITION_LEVEL",
                    "Competition level",
                    _level_decimal(row, row_number, "competition_level", loaded.result.errors),
                ),
                _market_indicator(
                    country_code,
                    country_name,
                    "LOGISTICS_DIFFICULTY",
                    "Logistics difficulty",
                    _level_decimal(row, row_number, "logistics_difficulty", loaded.result.errors),
                ),
            ]
        )

    return _insert_objects(db, loaded.result, indicators, mode)


def import_trade_samples(
    db: Session,
    *,
    file_name: str | None = None,
    mode: ImportMode = "insert",
    seed_dir: Path | None = None,
) -> CsvImportResult:
    loaded = _load_csv(
        "trade-samples",
        "trade_samples.csv",
        mode,
        required_headers={
            "hs_code",
            "product_category",
            "reporter",
            "partner",
            "year",
            "flow",
            "trade_value_usd",
            "quantity",
            "source",
        },
        file_name=file_name,
        seed_dir=seed_dir,
    )

    stats: list[TradeStat] = []
    for row_number, row in loaded.rows:
        stats.append(
            TradeStat(
                hs_code=_required_text(row, row_number, "hs_code", loaded.result.errors),
                product_category=_optional_text(row, "product_category"),
                reporter=_required_text(row, row_number, "reporter", loaded.result.errors),
                partner=_required_text(row, row_number, "partner", loaded.result.errors),
                year=_required_int(row, row_number, "year", loaded.result.errors),
                flow=_required_text(row, row_number, "flow", loaded.result.errors),
                trade_value_usd=_optional_decimal(row, row_number, "trade_value_usd", loaded.result.errors),
                quantity=_optional_decimal(row, row_number, "quantity", loaded.result.errors),
                source=_optional_text(row, "source") or "UN Comtrade Sample",
            )
        )

    return _insert_objects(db, loaded.result, stats, mode)


def import_content_trends(
    db: Session,
    *,
    file_name: str | None = None,
    mode: ImportMode = "insert",
    seed_dir: Path | None = None,
) -> CsvImportResult:
    loaded = _load_csv(
        "content-trends",
        "content_trends.csv",
        mode,
        required_headers={
            "platform",
            "country",
            "keyword",
            "title",
            "url",
            "channel_or_community",
            "published_at",
            "heat_score",
            "summary",
            "content_style",
        },
        file_name=file_name,
        seed_dir=seed_dir,
    )

    trends: list[ContentTrend] = []
    for row_number, row in loaded.rows:
        trends.append(_content_trend_from_row(row, row_number, loaded.result.errors))

    return _insert_objects(db, loaded.result, trends, mode)


def import_user_discussions(
    db: Session,
    *,
    file_name: str | None = None,
    mode: ImportMode = "insert",
    seed_dir: Path | None = None,
) -> CsvImportResult:
    loaded = _load_csv(
        "user-discussions",
        "user_discussions.csv",
        mode,
        required_headers={
            "discussion_id",
            "platform",
            "country",
            "keyword",
            "topic_title",
            "community",
            "discussion_summary",
            "sentiment",
            "pain_point",
            "desired_feature",
            "purchase_intent",
            "interaction_count",
            "published_at",
            "url",
        },
        file_name=file_name,
        seed_dir=seed_dir,
    )

    trends: list[ContentTrend] = []
    for row_number, row in loaded.rows:
        summary_parts = [
            _optional_text(row, "discussion_summary"),
            f"Pain point: {_optional_text(row, 'pain_point')}" if _optional_text(row, "pain_point") else None,
            f"Desired feature: {_optional_text(row, 'desired_feature')}"
            if _optional_text(row, "desired_feature")
            else None,
            f"Purchase intent: {_optional_text(row, 'purchase_intent')}"
            if _optional_text(row, "purchase_intent")
            else None,
            f"Sentiment: {_optional_text(row, 'sentiment')}" if _optional_text(row, "sentiment") else None,
        ]
        trends.append(
            ContentTrend(
                platform=_required_text(row, row_number, "platform", loaded.result.errors),
                country=_optional_text(row, "country"),
                keyword=_required_text(row, row_number, "keyword", loaded.result.errors),
                title=_required_text(row, row_number, "topic_title", loaded.result.errors),
                url=_optional_text(row, "url"),
                channel_or_community=_optional_text(row, "community"),
                published_at=_optional_datetime(row, row_number, "published_at", loaded.result.errors),
                heat_score=_optional_decimal(row, row_number, "interaction_count", loaded.result.errors),
                summary=" ".join(part for part in summary_parts if part),
                content_style="user_discussion",
            )
        )

    return _insert_objects(db, loaded.result, trends, mode)


class _LoadedCsv:
    def __init__(
        self,
        result: CsvImportResult,
        rows: list[tuple[int, dict[str, str]]],
    ) -> None:
        self.result = result
        self.rows = rows


def _load_csv(
    dataset: str,
    default_file_name: str,
    mode: ImportMode,
    *,
    required_headers: set[str],
    file_name: str | None,
    seed_dir: Path | None,
) -> _LoadedCsv:
    path = _resolve_seed_file(file_name or default_file_name, seed_dir=seed_dir)
    result = _empty_result(dataset, path.name, mode)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            fieldnames = [field.strip() for field in reader.fieldnames or []]
            missing_headers = sorted(required_headers.difference(fieldnames))
            if missing_headers:
                result.errors.append(
                    CsvImportErrorDetail(
                        row_number=1,
                        field="header",
                        message=f"Missing required CSV columns: {', '.join(missing_headers)}",
                    )
                )
                result.failed = 1
                raise CsvImportValidationError(result)
            rows = [
                (row_number, _clean_row(row))
                for row_number, row in enumerate(reader, start=2)
                if not _is_blank_row(row)
            ]
    except UnicodeDecodeError as exc:
        raise CsvImportRequestError("CSV file must be UTF-8 encoded") from exc
    except csv.Error as exc:
        raise CsvImportRequestError(f"CSV parse failed: {exc}") from exc

    result.total_rows = len(rows)
    return _LoadedCsv(result=result, rows=rows)


def _resolve_seed_file(file_name: str, *, seed_dir: Path | None = None) -> Path:
    base_dir = (seed_dir or DEFAULT_SEED_DIR).resolve()
    requested = Path(file_name)
    if requested.is_absolute():
        raise CsvImportRequestError("file_name must be relative to data/seed")
    candidate = (base_dir / requested).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise CsvImportRequestError("file_name must stay within data/seed") from exc
    if candidate.suffix.lower() != ".csv":
        raise CsvImportRequestError("file_name must point to a .csv file")
    if not candidate.exists() or not candidate.is_file():
        raise CsvImportRequestError(f"CSV file not found: {requested.as_posix()}", 404)
    return candidate


def _empty_result(dataset: str, file_name: str, mode: ImportMode) -> CsvImportResult:
    return CsvImportResult(
        dataset=dataset,
        file_name=file_name,
        mode=mode,
        total_rows=0,
        valid_rows=0,
        inserted=0,
        failed=0,
    )


def _clean_row(row: dict[str, str | list[str] | None]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        cleaned[key.strip()] = "" if value is None or isinstance(value, list) else value.strip()
    return cleaned


def _is_blank_row(row: dict[str, str | list[str] | None]) -> bool:
    return all(value is None or value == "" for key, value in row.items() if key is not None)


def _insert_objects(
    db: Session,
    result: CsvImportResult,
    objects: Iterable[object],
    mode: ImportMode,
) -> CsvImportResult:
    objects_list = list(objects)
    _raise_if_errors(result)
    if mode == "validate":
        result.valid_rows = result.total_rows
        return result

    try:
        db.add_all(objects_list)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise CsvImportRequestError(f"Database insert failed during {result.dataset} import", 500) from exc

    result.valid_rows = result.total_rows
    result.inserted = len(objects_list)
    return result


def _raise_if_errors(result: CsvImportResult) -> None:
    if result.errors:
        row_numbers = {error.row_number for error in result.errors if error.row_number and error.row_number > 1}
        result.failed = len(row_numbers) or len(result.errors)
        result.valid_rows = max(result.total_rows - result.failed, 0)
        raise CsvImportValidationError(result)


def _required_text(
    row: dict[str, str],
    row_number: int,
    field: str,
    errors: list[CsvImportErrorDetail],
) -> str:
    value = _optional_text(row, field)
    if value is None:
        errors.append(
            CsvImportErrorDetail(
                row_number=row_number,
                field=field,
                message="Field is required",
                raw_value=row.get(field),
            )
        )
        return ""
    return value


def _optional_text(row: dict[str, str], field: str) -> str | None:
    value = row.get(field)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _required_int(
    row: dict[str, str],
    row_number: int,
    field: str,
    errors: list[CsvImportErrorDetail],
) -> int:
    value = _optional_int(row, row_number, field, errors)
    if value is None:
        errors.append(
            CsvImportErrorDetail(
                row_number=row_number,
                field=field,
                message="Integer field is required",
                raw_value=row.get(field),
            )
        )
        return 0
    return value


def _optional_int(
    row: dict[str, str],
    row_number: int,
    field: str,
    errors: list[CsvImportErrorDetail],
) -> int | None:
    value = _optional_text(row, field)
    if value is None:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        errors.append(
            CsvImportErrorDetail(
                row_number=row_number,
                field=field,
                message="Invalid integer value",
                raw_value=value,
            )
        )
        return None


def _optional_decimal(
    row: dict[str, str],
    row_number: int,
    field: str,
    errors: list[CsvImportErrorDetail],
) -> Decimal | None:
    value = _optional_text(row, field)
    if value is None:
        return None
    normalized = re.sub(r"[$£¥,％%]", "", value)
    try:
        return Decimal(normalized)
    except InvalidOperation:
        errors.append(
            CsvImportErrorDetail(
                row_number=row_number,
                field=field,
                message="Invalid decimal value",
                raw_value=value,
            )
        )
        return None


def _optional_datetime(
    row: dict[str, str],
    row_number: int,
    field: str,
    errors: list[CsvImportErrorDetail],
) -> datetime | None:
    value = _optional_text(row, field)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(
            CsvImportErrorDetail(
                row_number=row_number,
                field=field,
                message="Invalid ISO datetime value",
                raw_value=value,
            )
        )
        return None


def _split_keywords(value: str | None) -> list[str]:
    if value is None:
        return []
    return [keyword.strip() for keyword in re.split(r"[;|,]", value) if keyword.strip()]


def _level_decimal(
    row: dict[str, str],
    row_number: int,
    field: str,
    errors: list[CsvImportErrorDetail],
) -> Decimal | None:
    value = _optional_text(row, field)
    if value is None:
        return None
    level_map = {
        "low": Decimal("1"),
        "medium": Decimal("2"),
        "high": Decimal("3"),
    }
    normalized = value.lower()
    if normalized not in level_map:
        errors.append(
            CsvImportErrorDetail(
                row_number=row_number,
                field=field,
                message="Invalid level value. Expected low, medium, or high",
                raw_value=value,
            )
        )
        return None
    return level_map[normalized]


def _market_indicator(
    country_code: str,
    country_name: str,
    indicator_code: str,
    indicator_name: str,
    value: Decimal | None,
) -> MarketIndicator:
    return MarketIndicator(
        country_code=country_code,
        country_name=country_name,
        indicator_code=indicator_code,
        indicator_name=indicator_name,
        value=value,
        year=2025,
        source="CSV Market Profile Sample",
    )


def _content_trend_from_row(
    row: dict[str, str],
    row_number: int,
    errors: list[CsvImportErrorDetail],
) -> ContentTrend:
    return ContentTrend(
        platform=_required_text(row, row_number, "platform", errors),
        country=_optional_text(row, "country"),
        keyword=_required_text(row, row_number, "keyword", errors),
        title=_required_text(row, row_number, "title", errors),
        url=_optional_text(row, "url"),
        channel_or_community=_optional_text(row, "channel_or_community"),
        published_at=_optional_datetime(row, row_number, "published_at", errors),
        heat_score=_optional_decimal(row, row_number, "heat_score", errors),
        summary=_optional_text(row, "summary"),
        content_style=_optional_text(row, "content_style"),
    )
