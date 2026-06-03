from __future__ import annotations

import csv
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.schemas import (
    AnalysisSource,
    ContentTrendAnalysisResponse,
    ContentTrendSourceItem,
    DataSourceContentTrendItem,
    DataSourceContentTrendResponse,
)
from app.services.ai import BailianClient, BailianError
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_content_trend_analysis_messages
from app.services.analysis_performance import mark_latest_qwen_fallback
from app.services.data_sources import DataSourceService
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
SAMPLE_ONLY_PLATFORMS = {"TikTok Sample", "Pinterest Sample"}


class ContentTrendAnalysisService:
    def __init__(
        self,
        data_source_service: DataSourceService,
        *,
        ai_client: BailianClient | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._data_sources = data_source_service
        self._ai_client = ai_client or BailianClient()
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    async def analyze(self, keyword: str, country: str) -> ContentTrendAnalysisResponse:
        normalized_keyword = _normalize_text(keyword)
        normalized_country = _normalize_country(country)
        data_response, service_failed = await self._trend_data(normalized_keyword, normalized_country)
        source_items = _source_items_from_response(data_response)
        source_items.extend(_discussion_source_items(normalized_keyword, normalized_country, self._seed_dir))

        if not source_items:
            source_items = _csv_content_source_items(normalized_keyword, normalized_country, self._seed_dir)
            service_failed = True

        source_items = _dedupe_items(source_items)
        source_items.sort(key=_source_item_sort_key)
        source_items = source_items[:40]

        fallback_analysis = _deterministic_analysis(normalized_keyword, normalized_country, source_items, service_failed)
        ai_analysis, ai_fallback_used = await self._ai_analysis(
            normalized_keyword,
            normalized_country,
            source_items,
            fallback_analysis,
        )
        sources = _trend_sources(source_items, data_response, service_failed, ai_fallback_used)
        return ContentTrendAnalysisResponse(
            keyword=normalized_keyword,
            country=normalized_country,
            content_themes=ai_analysis["content_themes"],
            marketing_angles=ai_analysis["marketing_angles"],
            pain_points=ai_analysis["pain_points"],
            video_script_ideas=ai_analysis["video_script_ideas"],
            pinterest_keywords=ai_analysis["pinterest_keywords"],
            risk_notes=ai_analysis["risk_notes"],
            source_items=source_items,
            fallback_used=service_failed or data_response.fallback_used,
            ai_fallback_used=ai_fallback_used,
            sources=sources,
        )

    async def _trend_data(self, keyword: str, country: str) -> tuple[DataSourceContentTrendResponse, bool]:
        try:
            response = await self._data_sources.get_content_trends(keyword, country=country, limit=50)
            return response, False
        except Exception:
            return DataSourceContentTrendResponse(
                keyword=keyword,
                country=country,
                items=_csv_fallback_items(keyword, country, self._seed_dir),
                fallback_used=True,
                sources=["CSV fallback"],
            ), True

    async def _ai_analysis(
        self,
        keyword: str,
        country: str,
        source_items: list[ContentTrendSourceItem],
        fallback_analysis: dict[str, list[str]],
    ) -> tuple[dict[str, list[str]], bool]:
        payload = {
            "keyword": keyword,
            "country": country,
            "source_items": [item.model_dump(mode="json") for item in source_items[:25]],
            "fallback_analysis": fallback_analysis,
        }
        try:
            result = await self._ai_client.chat(
                build_content_trend_analysis_messages(payload),
                temperature=0.4,
                max_tokens=1200,
                json_mode=True,
            )
            parsed = parse_json_object(result.content)
            return _validated_analysis(parsed, fallback_analysis), False
        except (BailianError, AiJsonParseError, ValueError, TypeError):
            mark_latest_qwen_fallback("content_trend_analysis")
            return fallback_analysis, True


def _source_items_from_response(response: DataSourceContentTrendResponse) -> list[ContentTrendSourceItem]:
    return [_source_item_from_trend_item(item) for item in response.items]


def _source_item_from_trend_item(item: DataSourceContentTrendItem) -> ContentTrendSourceItem:
    source_type = item.source_type or CSV_FALLBACK_SOURCE
    api_invoked = source_type == API_SOURCE and item.platform not in SAMPLE_ONLY_PLATFORMS
    fallback_used = source_type != API_SOURCE
    return ContentTrendSourceItem(
        platform=item.platform,
        country=item.country,
        keyword=item.keyword,
        title=item.title,
        url=item.url,
        channel_or_community=item.channel_or_community,
        published_at=item.published_at,
        heat_score=item.heat_score,
        summary=item.summary,
        content_style=item.content_style,
        source_type=source_type,
        source_label=_source_label(item.platform, source_type),
        api_invoked=api_invoked,
        fallback_used=fallback_used,
        sample_notice=_sample_notice(item.platform),
    )


def _discussion_source_items(keyword: str, country: str, seed_dir: Path) -> list[ContentTrendSourceItem]:
    rows = _ranked_discussion_rows(keyword, country, seed_dir)
    items: list[ContentTrendSourceItem] = []
    for row in rows[:20]:
        pain_point = row.get("pain_point") or ""
        desired_feature = row.get("desired_feature") or ""
        summary_parts = [
            row.get("discussion_summary") or "",
            f"Pain point: {pain_point}" if pain_point else "",
            f"Desired feature: {desired_feature}" if desired_feature else "",
            f"Purchase intent: {row.get('purchase_intent')}" if row.get("purchase_intent") else "",
            f"Sentiment: {row.get('sentiment')}" if row.get("sentiment") else "",
        ]
        platform = row.get("platform") or "Discussion Sample"
        items.append(
            ContentTrendSourceItem(
                platform=platform,
                country=(row.get("country") or country).upper(),
                keyword=row.get("keyword") or keyword,
                title=row.get("topic_title") or row.get("keyword") or keyword,
                url=row.get("url") or None,
                channel_or_community=row.get("community") or None,
                published_at=row.get("published_at") or None,
                heat_score=_decimal_from_any(row.get("interaction_count")),
                summary=" ".join(part for part in summary_parts if part),
                content_style="user_discussion",
                source_type=CSV_FALLBACK_SOURCE,
                source_label=f"CSV fallback: {platform}",
                api_invoked=False,
                fallback_used=True,
                sample_notice="Synthetic sample discussion; no live Reddit or forum API call.",
            )
        )
    return items


def _csv_content_source_items(keyword: str, country: str, seed_dir: Path) -> list[ContentTrendSourceItem]:
    return [_source_item_from_trend_item(item) for item in _csv_fallback_items(keyword, country, seed_dir)]


def _csv_fallback_items(keyword: str, country: str, seed_dir: Path) -> list[DataSourceContentTrendItem]:
    rows = _ranked_content_rows(keyword, country, seed_dir)
    return [
        DataSourceContentTrendItem(
            platform=row.get("platform") or "CSV Sample",
            country=(row.get("country") or country).upper(),
            keyword=row.get("keyword") or keyword,
            title=row.get("title") or keyword,
            url=row.get("url") or None,
            channel_or_community=row.get("channel_or_community") or None,
            published_at=row.get("published_at") or None,
            heat_score=_decimal_from_any(row.get("heat_score")),
            summary=row.get("summary") or None,
            content_style=row.get("content_style") or None,
            source_type=CSV_FALLBACK_SOURCE,
        )
        for row in rows[:30]
    ]


def _deterministic_analysis(
    keyword: str,
    country: str,
    source_items: list[ContentTrendSourceItem],
    service_failed: bool,
) -> dict[str, list[str]]:
    themes = _top_values([_readable_label(item.content_style) for item in source_items if item.content_style], 5)
    if not themes:
        themes = [f"{keyword} product education", f"{keyword} lifestyle inspiration"]

    pain_points = _extract_pain_points(source_items)
    if not pain_points:
        pain_points = [f"Buyers need clearer material, care, and sizing information for {keyword}."]

    pinterest_keywords = _top_values(
        [
            item.keyword
            for item in source_items
            if "pinterest" in item.platform.casefold() or (item.content_style or "").casefold() in {"mood_board", "room_makeover"}
        ],
        8,
    )
    if not pinterest_keywords:
        pinterest_keywords = [f"{keyword} inspiration", f"{keyword} home decor", f"{keyword} ideas"]

    marketing_angles = [
        f"Lead with the strongest buyer pain point: {pain_points[0]}",
        f"Localize visuals around {country} use cases and seasonal shopping moments.",
        "Show material, washing, package size, and usage scenarios with concrete evidence.",
    ]
    video_script_ideas = [
        f"Before and after setup using {keyword} in a real room or daily routine.",
        f"30-second checklist: how to choose {keyword} by material, size, and care needs.",
        f"Problem-solution demo addressing: {pain_points[0]}",
    ]
    risk_notes = [
        "TikTok and Pinterest signals are CSV samples only; no live TikTok/Pinterest API was called.",
        "Avoid unverifiable performance, medical, safety, or certification claims in marketing copy.",
    ]
    if service_failed or any(item.fallback_used for item in source_items):
        risk_notes.append("Some trend evidence uses CSV fallback/sample data; treat analysis as directional.")

    return {
        "content_themes": _clean_list(themes),
        "marketing_angles": _clean_list(marketing_angles),
        "pain_points": _clean_list(pain_points),
        "video_script_ideas": _clean_list(video_script_ideas),
        "pinterest_keywords": _clean_list(pinterest_keywords),
        "risk_notes": _clean_list(risk_notes),
    }


def _validated_analysis(parsed: dict[str, Any], fallback: dict[str, list[str]]) -> dict[str, list[str]]:
    fields = (
        "content_themes",
        "marketing_angles",
        "pain_points",
        "video_script_ideas",
        "pinterest_keywords",
        "risk_notes",
    )
    result: dict[str, list[str]] = {}
    for field in fields:
        values = parsed.get(field)
        cleaned = _clean_list(values if isinstance(values, list) else [])
        result[field] = cleaned or fallback[field]
    return result


def _trend_sources(
    source_items: list[ContentTrendSourceItem],
    response: DataSourceContentTrendResponse,
    service_failed: bool,
    ai_fallback_used: bool,
) -> list[AnalysisSource]:
    sources: dict[tuple[str, str, str], AnalysisSource] = {}
    for item in source_items:
        provider = _provider_for_platform(item.platform)
        source = AnalysisSource(
            provider=provider,
            source_label=item.source_label,
            source_type=item.source_type,
            fallback_used=item.fallback_used,
            api_invoked=item.api_invoked,
            detail=item.sample_notice,
        )
        key = (source.provider, source.source_label, source.source_type)
        existing = sources.get(key)
        if existing is None:
            sources[key] = source
        else:
            existing.fallback_used = existing.fallback_used or source.fallback_used
            existing.api_invoked = existing.api_invoked or source.api_invoked

    sources[("data_source_service", "Unified DataSourceService", "mixed")] = AnalysisSource(
        provider="data_source_service",
        source_label="Unified DataSourceService",
        source_type="mixed",
        fallback_used=service_failed or response.fallback_used,
        api_invoked=any(item.api_invoked for item in source_items),
        detail="Orchestrates YouTube, GDELT, and CSV fallback trend rows.",
    )
    sources[("bailian", "qwen3.6-plus" if not ai_fallback_used else "AI fallback template", "api")] = AnalysisSource(
        provider="bailian",
        source_label="qwen3.6-plus" if not ai_fallback_used else "AI fallback template",
        source_type=API_SOURCE if not ai_fallback_used else "ai_fallback",
        fallback_used=ai_fallback_used,
        api_invoked=not ai_fallback_used,
        detail="Structured trend interpretation.",
    )
    return list(sources.values())


def _ranked_content_rows(keyword: str, country: str, seed_dir: Path) -> list[dict[str, str]]:
    aliases = {keyword, *_keyword_aliases(keyword)}
    ranked: list[tuple[int, Decimal, str, dict[str, str]]] = []
    for row in _read_csv_rows(seed_dir / "content_trends.csv"):
        row_keyword = _normalize_text(row.get("keyword", ""))
        row_country = row.get("country", "").upper()
        keyword_match = row_keyword in aliases
        country_match = row_country == country
        if keyword_match and country_match:
            rank = 0
        elif keyword_match:
            rank = 1
        elif country_match:
            rank = 2
        else:
            rank = 3
        ranked.append((rank, _decimal_from_any(row.get("heat_score")) or Decimal("0"), row.get("published_at", ""), row))
    ranked.sort(key=lambda item: (item[0], -item[1], item[2]), reverse=False)
    return [row for _rank, _heat, _published, row in ranked]


def _ranked_discussion_rows(keyword: str, country: str, seed_dir: Path) -> list[dict[str, str]]:
    aliases = {keyword, *_keyword_aliases(keyword)}
    ranked: list[tuple[int, Decimal, str, dict[str, str]]] = []
    for row in _read_csv_rows(seed_dir / "user_discussions.csv"):
        row_keyword = _normalize_text(row.get("keyword", ""))
        row_country = row.get("country", "").upper()
        keyword_match = row_keyword in aliases
        country_match = row_country == country
        if keyword_match and country_match:
            rank = 0
        elif keyword_match:
            rank = 1
        elif country_match:
            rank = 2
        else:
            rank = 3
        ranked.append((rank, _decimal_from_any(row.get("interaction_count")) or Decimal("0"), row.get("published_at", ""), row))
    ranked.sort(key=lambda item: (item[0], -item[1], item[2]), reverse=False)
    return [row for _rank, _interaction, _published, row in ranked]


def _keyword_aliases(keyword: str) -> tuple[str, ...]:
    aliases: dict[str, tuple[str, ...]] = {
        "home textile": (
            "home decor",
            "cotton bedding set",
            "sofa throw",
            "bath towel",
            "cooling quilt",
            "anti mite pillowcase",
            "baby swaddle",
            "dorm room bedding",
            "boho bedroom",
        ),
        "boho blanket": ("boho bedroom", "home decor"),
        "cooling blanket": ("cooling quilt", "summer quilt"),
        "baby swaddle blanket": ("baby swaddle",),
        "sofa throw blanket": ("sofa throw",),
        "allergy bedding": ("anti allergy bedding", "anti mite pillowcase"),
        "pet products": ("pet cooling mat", "pet summer care"),
    }
    return aliases.get(keyword, ())


def _source_label(platform: str, source_type: str) -> str:
    if source_type == API_SOURCE and platform.casefold() == "youtube":
        return "YouTube API"
    if source_type == API_SOURCE and platform.casefold() == "gdelt":
        return "GDELT API"
    if source_type == API_SOURCE:
        return f"{platform} API"
    sample_platform = platform if platform.endswith("Sample") else f"{platform} Sample"
    return f"CSV fallback: {sample_platform}"


def _provider_for_platform(platform: str) -> str:
    lowered = platform.casefold()
    if "youtube" in lowered:
        return "youtube"
    if "gdelt" in lowered:
        return "gdelt"
    if "tiktok" in lowered:
        return "csv_tiktok_sample"
    if "pinterest" in lowered:
        return "csv_pinterest_sample"
    if "reddit" in lowered or "forum" in lowered:
        return "csv_discussion_sample"
    return "csv_content_sample"


def _sample_notice(platform: str) -> str | None:
    if platform in SAMPLE_ONLY_PLATFORMS:
        return f"{platform} is a synthetic CSV sample; no live TikTok/Pinterest API call."
    if platform.endswith("Sample"):
        return f"{platform} is a CSV sample row."
    return None


def _dedupe_items(items: list[ContentTrendSourceItem]) -> list[ContentTrendSourceItem]:
    deduped: dict[str, ContentTrendSourceItem] = {}
    for item in items:
        key = f"url:{item.url.lower()}" if item.url else f"text:{item.platform}:{item.country}:{_normalize_text(item.title)}"
        existing = deduped.get(key)
        if existing is None or _prefer_item(item, existing):
            deduped[key] = item
    return list(deduped.values())


def _prefer_item(left: ContentTrendSourceItem, right: ContentTrendSourceItem) -> bool:
    if left.api_invoked != right.api_invoked:
        return left.api_invoked
    return (left.heat_score or Decimal("0")) > (right.heat_score or Decimal("0"))


def _source_item_sort_key(item: ContentTrendSourceItem) -> tuple[int, Decimal, str]:
    return (
        0 if item.api_invoked else 1,
        -(item.heat_score or Decimal("0")),
        item.published_at or "",
    )


def _top_values(values: list[str], limit: int) -> list[str]:
    counter = Counter(value for value in values if value)
    return [value for value, _count in counter.most_common(limit)]


def _extract_pain_points(items: list[ContentTrendSourceItem]) -> list[str]:
    points: list[str] = []
    for item in items:
        summary = item.summary or ""
        marker = "Pain point:"
        if marker in summary:
            points.append(summary.split(marker, 1)[1].split("Desired feature:", 1)[0].strip())
    return _clean_list(points)[:6]


def _readable_label(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("_", " ").strip()


def _clean_list(values: list[object]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = " ".join(value.strip().split())
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned


def _normalize_text(value: str) -> str:
    normalized = " ".join(value.strip().split()).lower()
    if not normalized:
        raise ValueError("Keyword must not be empty")
    return normalized


def _normalize_country(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) not in {2, 3} or not normalized.isalpha():
        raise ValueError("Country must be a two- or three-letter code")
    return normalized


def _decimal_from_any(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


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
