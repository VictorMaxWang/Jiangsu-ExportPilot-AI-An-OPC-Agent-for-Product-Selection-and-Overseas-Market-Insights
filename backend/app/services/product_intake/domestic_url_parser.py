from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


DomesticPlatform = Literal["taobao", "tmall", "jd", "pinduoduo", "unknown"]
DomesticUrlParseStatus = Literal[
    "parsed",
    "invalid_url",
    "invalid_scheme",
    "blocked_host",
    "unsupported_domain",
    "missing_item_id",
]

ALLOWED_DOMAINS = ("taobao.com", "tmall.com", "jd.com", "pinduoduo.com", "yangkeduo.com")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
JD_SKU_PATH_RE = re.compile(r"/(?:product/)?([0-9]{5,})\.html/?$")
PDD_PATH_RE = re.compile(r"/(?:goods|goods1|duo_goods)/([A-Za-z0-9_-]{3,128})(?:/|$)")
BLOCKED_LITERAL_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}


@dataclass(frozen=True)
class DomesticUrlParseResult:
    platform: DomesticPlatform
    original_url: str
    normalized_url: str
    item_id: str
    sku_id: str
    parse_status: DomesticUrlParseStatus


def parse_domestic_product_url(raw_url: str) -> DomesticUrlParseResult:
    original_url = str(raw_url or "").strip()
    if not original_url or len(original_url) > 2048:
        return _result(original_url, parse_status="invalid_url")

    try:
        parsed = urlsplit(original_url)
    except ValueError:
        return _result(original_url, parse_status="invalid_url")

    if parsed.scheme.lower() not in {"http", "https"}:
        return _result(original_url, parse_status="invalid_scheme")
    if parsed.username or parsed.password:
        return _result(original_url, parse_status="blocked_host")

    host = normalize_host(parsed.hostname)
    if not host:
        return _result(original_url, parse_status="invalid_url")
    if is_blocked_hostname(host):
        return _result(original_url, parse_status="blocked_host")

    try:
        port = parsed.port
    except ValueError:
        return _result(original_url, parse_status="blocked_host")
    if port not in {None, 80, 443}:
        return _result(original_url, parse_status="blocked_host")

    platform = detect_platform(host)
    if platform == "unknown":
        return _result(original_url, parse_status="unsupported_domain")

    item_id, sku_id = extract_item_ids(platform, parsed.path, parsed.query)
    if platform == "jd" and sku_id and not item_id:
        item_id = sku_id
    if not item_id and not sku_id:
        return _result(original_url, platform=platform, parse_status="missing_item_id")

    normalized_url = build_normalized_url(platform, item_id=item_id, sku_id=sku_id)
    if not normalized_url:
        return _result(original_url, platform=platform, parse_status="missing_item_id")

    return _result(
        original_url,
        platform=platform,
        normalized_url=normalized_url,
        item_id=item_id,
        sku_id=sku_id,
        parse_status="parsed",
    )


def normalize_host(hostname: str | None) -> str:
    return str(hostname or "").strip().rstrip(".").lower()


def is_supported_domestic_host(hostname: str) -> bool:
    host = normalize_host(hostname)
    return any(host == domain or host.endswith(f".{domain}") for domain in ALLOWED_DOMAINS)


def detect_platform(hostname: str) -> DomesticPlatform:
    host = normalize_host(hostname)
    if host == "tmall.com" or host.endswith(".tmall.com"):
        return "tmall"
    if host == "taobao.com" or host.endswith(".taobao.com"):
        return "taobao"
    if host == "jd.com" or host.endswith(".jd.com"):
        return "jd"
    if (
        host == "pinduoduo.com"
        or host.endswith(".pinduoduo.com")
        or host == "yangkeduo.com"
        or host.endswith(".yangkeduo.com")
    ):
        return "pinduoduo"
    return "unknown"


def is_blocked_hostname(hostname: str) -> bool:
    host = normalize_host(hostname)
    if not host:
        return True
    if host == "localhost" or host.endswith(".localhost"):
        return True

    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return _is_blocked_ip(ip)


def extract_item_ids(platform: DomesticPlatform, path: str, query: str) -> tuple[str, str]:
    values = _query_values_by_lower(query)
    if platform in {"taobao", "tmall"}:
        item_id = _first_query_value(values, ("id", "item_id", "itemid"))
        sku_id = _first_query_value(values, ("skuid", "sku_id", "sku"))
        return item_id, sku_id
    if platform == "jd":
        path_match = JD_SKU_PATH_RE.search(path or "")
        sku_id = _clean_id(path_match.group(1)) if path_match else ""
        sku_id = sku_id or _first_query_value(values, ("sku", "skuid", "wareid", "productid", "itemid", "id"))
        return sku_id, sku_id
    if platform == "pinduoduo":
        item_id = _first_query_value(values, ("goods_id", "goodsid", "item_id", "itemid"))
        if not item_id:
            path_match = PDD_PATH_RE.search(path or "")
            item_id = _clean_id(path_match.group(1)) if path_match else ""
        sku_id = _first_query_value(values, ("sku_id", "skuid", "sku"))
        return item_id, sku_id
    return "", ""


def build_normalized_url(platform: DomesticPlatform, *, item_id: str, sku_id: str) -> str:
    if platform == "taobao" and item_id:
        return _with_query("https", "item.taobao.com", "/item.htm", {"id": item_id, "skuId": sku_id})
    if platform == "tmall" and item_id:
        return _with_query("https", "detail.tmall.com", "/item.htm", {"id": item_id, "skuId": sku_id})
    if platform == "jd" and sku_id:
        return urlunsplit(("https", "item.jd.com", f"/{sku_id}.html", "", ""))
    if platform == "pinduoduo" and item_id:
        return _with_query("https", "mobile.yangkeduo.com", "/goods.html", {"goods_id": item_id, "sku_id": sku_id})
    return ""


def _result(
    original_url: str,
    *,
    platform: DomesticPlatform = "unknown",
    normalized_url: str = "",
    item_id: str = "",
    sku_id: str = "",
    parse_status: DomesticUrlParseStatus,
) -> DomesticUrlParseResult:
    return DomesticUrlParseResult(
        platform=platform,
        original_url=original_url[:2048],
        normalized_url=normalized_url[:2048],
        item_id=item_id[:128],
        sku_id=sku_id[:128],
        parse_status=parse_status,
    )


def _query_values_by_lower(query: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for key, items in parse_qs(query, keep_blank_values=False).items():
        values.setdefault(key.lower(), []).extend(items)
    return values


def _first_query_value(values: dict[str, list[str]], keys: tuple[str, ...]) -> str:
    for key in keys:
        for value in values.get(key.lower(), []):
            cleaned = _clean_id(value)
            if cleaned:
                return cleaned
    return ""


def _clean_id(value: object) -> str:
    text = str(value or "").strip()
    return text if SAFE_ID_RE.fullmatch(text) else ""


def _with_query(scheme: str, host: str, path: str, params: dict[str, str]) -> str:
    safe_params = {key: value for key, value in params.items() if value}
    return urlunsplit((scheme, host, path, urlencode(safe_params), ""))


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip in BLOCKED_LITERAL_IPS:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )
