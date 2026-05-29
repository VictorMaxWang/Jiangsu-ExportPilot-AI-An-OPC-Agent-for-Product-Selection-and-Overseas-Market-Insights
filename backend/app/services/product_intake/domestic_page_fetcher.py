from __future__ import annotations

import asyncio
import inspect
import ipaddress
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx

from app.services.product_intake.domestic_url_parser import (
    DomesticPlatform,
    is_blocked_hostname,
    is_supported_domestic_host,
)
from app.utils.redaction import redact_text


DomesticFetchStatus = Literal["parsed", "needs_screenshot"]
AddressResolver = Callable[[str, int], Awaitable[list[str]] | list[str]]

SCREENSHOT_MESSAGE = "请上传截图继续分析"
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000
DEFAULT_MAX_VISIBLE_TEXT_CHARS = 6000
DEFAULT_MAX_REDIRECTS = 3
BLOCKED_LITERAL_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}
SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}
RISK_KEYWORDS = (
    "请先登录",
    "登录后查看",
    "验证码",
    "滑块",
    "安全验证",
    "访问受限",
    "访问过于频繁",
    "异常流量",
    "系统检测到",
    "captcha",
    "verify",
    "blocked",
    "risk",
)
RISK_URL_MARKERS = ("login", "passport", "captcha", "x5sec", "sec.taobao.com", "verify")
PRICE_RE = re.compile(
    r"(?:[¥￥]\s*\d+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?\s*(?:元|RMB|CNY))",
    flags=re.IGNORECASE,
)
PRICE_CONTEXT_RE = re.compile(
    r"(?:价格|券后价|京东价|拼单价|促销价|到手价|售价|price)[^\n\r。；;]{0,24}?"
    r"(?:[¥￥]?\s*\d+(?:\.\d{1,2})?\s*(?:元|RMB|CNY)?)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class DomesticPageFetchInput:
    platform: DomesticPlatform
    original_url: str
    normalized_url: str
    item_id: str | None = None
    sku_id: str | None = None


@dataclass(frozen=True)
class DomesticPageFetchResult:
    parse_status: DomesticFetchStatus
    title: str | None = None
    meta_description: str | None = None
    og_title: str | None = None
    og_image: str | None = None
    visible_text: str = ""
    price_candidates: list[str] = field(default_factory=list)
    product_name_candidates: list[str] = field(default_factory=list)
    http_status: int | None = None
    final_url: str | None = None
    error_code: str | None = None
    message: str = ""
    truncated: bool = False


class DomesticPageFetchError(Exception):
    def __init__(self, code: str, message: str = SCREENSHOT_MESSAGE) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


async def fetch_domestic_product_page(
    parsed: DomesticPageFetchInput,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    resolver: AddressResolver | None = None,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_visible_text_chars: int = DEFAULT_MAX_VISIBLE_TEXT_CHARS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> DomesticPageFetchResult:
    if parsed.platform == "unknown" or not parsed.normalized_url:
        return _needs_screenshot("URL_PARSE_FAILED")

    current_url = parsed.normalized_url
    timeout = httpx.Timeout(8.0, connect=3.0, read=5.0, write=3.0, pool=3.0)
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "User-Agent": "SuPinZhiHangProductIntake/0.1",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            headers=headers,
        ) as client:
            for redirect_count in range(max_redirects + 1):
                await validate_fetch_target(current_url, resolver=resolver)
                async with client.stream("GET", current_url) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if redirect_count >= max_redirects:
                            return _needs_screenshot(
                                "URL_REDIRECT_LIMIT_EXCEEDED",
                                http_status=response.status_code,
                                final_url=current_url,
                            )
                        location = response.headers.get("location")
                        if not location:
                            return _needs_screenshot(
                                "URL_REDIRECT_TARGET_BLOCKED",
                                http_status=response.status_code,
                                final_url=current_url,
                            )
                        current_url = urljoin(current_url, location)
                        continue

                    if response.status_code >= 400:
                        return _needs_screenshot(
                            "URL_FETCH_BLOCKED",
                            http_status=response.status_code,
                            final_url=current_url,
                        )

                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and "text/html" not in content_type and "application/xhtml" not in content_type:
                        return _needs_screenshot(
                            "URL_CONTENT_TYPE_UNSUPPORTED",
                            http_status=response.status_code,
                            final_url=current_url,
                        )

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > max_response_bytes:
                            return _needs_screenshot(
                                "URL_RESPONSE_TOO_LARGE",
                                http_status=response.status_code,
                                final_url=current_url,
                                truncated=True,
                            )
                        body.extend(chunk)
                    return parse_domestic_product_html(
                        bytes(body),
                        http_status=response.status_code,
                        final_url=current_url,
                        max_visible_text_chars=max_visible_text_chars,
                    )
    except DomesticPageFetchError as exc:
        return _needs_screenshot(exc.code, final_url=current_url)
    except httpx.TimeoutException:
        return _needs_screenshot("URL_FETCH_TIMEOUT", final_url=current_url)
    except httpx.HTTPError:
        return _needs_screenshot("URL_FETCH_FAILED", final_url=current_url)

    return _needs_screenshot("URL_FETCH_FAILED", final_url=current_url)


async def validate_fetch_target(url: str, *, resolver: AddressResolver | None = None) -> None:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise DomesticPageFetchError("INVALID_URL") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise DomesticPageFetchError("URL_UNSUPPORTED_SCHEME")
    if parsed.username or parsed.password:
        raise DomesticPageFetchError("URL_PRIVATE_NETWORK_BLOCKED")
    host = str(parsed.hostname or "").strip().rstrip(".").lower()
    if not host:
        raise DomesticPageFetchError("INVALID_URL")
    if is_blocked_hostname(host):
        raise DomesticPageFetchError("URL_PRIVATE_NETWORK_BLOCKED")
    if not is_supported_domestic_host(host):
        raise DomesticPageFetchError("URL_HOST_NOT_ALLOWED")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise DomesticPageFetchError("URL_PRIVATE_NETWORK_BLOCKED") from exc
    if port not in {80, 443}:
        raise DomesticPageFetchError("URL_PRIVATE_NETWORK_BLOCKED")

    addresses = await resolve_public_addresses(host, port, resolver=resolver)
    if not addresses:
        raise DomesticPageFetchError("URL_DNS_RESOLUTION_FAILED")
    if any(_is_blocked_ip(address) for address in addresses):
        raise DomesticPageFetchError("URL_PRIVATE_NETWORK_BLOCKED")


async def resolve_public_addresses(
    host: str,
    port: int,
    *,
    resolver: AddressResolver | None = None,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    if resolver is not None:
        raw_result = resolver(host, port)
        if inspect.isawaitable(raw_result):
            raw_addresses = await raw_result
        else:
            raw_addresses = raw_result
        return [ipaddress.ip_address(str(address)) for address in raw_addresses]

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DomesticPageFetchError("URL_DNS_RESOLUTION_FAILED") from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        addresses.append(ipaddress.ip_address(str(sockaddr[0])))
    return addresses


def parse_domestic_product_html(
    html_bytes: bytes,
    *,
    http_status: int | None = None,
    final_url: str | None = None,
    max_visible_text_chars: int = DEFAULT_MAX_VISIBLE_TEXT_CHARS,
) -> DomesticPageFetchResult:
    html_text = _decode_html(html_bytes)
    parser = _ProductHtmlParser()
    parser.feed(html_text)
    parser.close()

    title = _clean_text(parser.title, max_length=512)
    meta_description = _clean_text(parser.meta_description, max_length=512)
    og_title = _clean_text(parser.og_title, max_length=512)
    og_image = _clean_og_image(parser.og_image)
    visible_text = _clean_text(" ".join(parser.visible_parts), max_length=max_visible_text_chars) or ""
    combined = " ".join(value for value in (title, meta_description, og_title, visible_text) if value)

    if _looks_blocked(final_url, combined):
        return _needs_screenshot("URL_PARSE_BLOCKED", http_status=http_status, final_url=final_url)

    product_name_candidates = _product_name_candidates(title, og_title, meta_description, parser.visible_parts)
    price_candidates = _price_candidates(combined)
    if not combined.strip() or (len(visible_text) < 20 and not product_name_candidates):
        return _needs_screenshot("URL_PARSE_FAILED", http_status=http_status, final_url=final_url)

    return DomesticPageFetchResult(
        parse_status="parsed",
        title=title,
        meta_description=meta_description,
        og_title=og_title,
        og_image=og_image,
        visible_text=visible_text,
        price_candidates=price_candidates,
        product_name_candidates=product_name_candidates,
        http_status=http_status,
        final_url=final_url,
        error_code=None,
        message="parsed",
    )


class _ProductHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.visible_parts: list[str] = []
        self.meta_description: str | None = None
        self.og_title: str | None = None
        self.og_image: str | None = None
        self._in_title = False
        self._skip_depth = 0

    @property
    def title(self) -> str:
        return " ".join(self.title_parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized == "title":
            self._in_title = True
        if normalized in SKIP_TAGS:
            self._skip_depth += 1
        if normalized == "meta":
            self._handle_meta(dict((key.lower(), value or "") for key, value in attrs))

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized == "title":
            self._in_title = False
        if normalized in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(str(data or "").split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
            return
        if self._skip_depth:
            return
        self.visible_parts.append(text)

    def _handle_meta(self, attrs: dict[str, str]) -> None:
        name = attrs.get("name", "").strip().lower()
        prop = attrs.get("property", "").strip().lower()
        content = attrs.get("content", "").strip()
        if not content:
            return
        if name == "description" and self.meta_description is None:
            self.meta_description = content
        elif prop == "og:title" and self.og_title is None:
            self.og_title = content
        elif prop == "og:image" and self.og_image is None:
            self.og_image = content


def _needs_screenshot(
    code: str,
    *,
    http_status: int | None = None,
    final_url: str | None = None,
    truncated: bool = False,
) -> DomesticPageFetchResult:
    return DomesticPageFetchResult(
        parse_status="needs_screenshot",
        http_status=http_status,
        final_url=final_url,
        error_code=code,
        message=SCREENSHOT_MESSAGE,
        truncated=truncated,
    )


def _decode_html(data: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _clean_text(value: object, *, max_length: int) -> str | None:
    text = redact_text(str(value or "")) or ""
    text = " ".join(text.split()).strip()
    if not text:
        return None
    return text[:max_length]


def _clean_og_image(value: object) -> str | None:
    text = str(value or "").strip()
    if not text.lower().startswith(("http://", "https://")):
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    return text[:2048]


def _looks_blocked(final_url: str | None, text: str) -> bool:
    lower_text = text.casefold()
    if any(keyword.casefold() in lower_text for keyword in RISK_KEYWORDS):
        return True
    lower_url = str(final_url or "").casefold()
    return any(marker in lower_url for marker in RISK_URL_MARKERS)


def _product_name_candidates(
    title: str | None,
    og_title: str | None,
    meta_description: str | None,
    visible_parts: list[str],
) -> list[str]:
    candidates: list[str] = []
    for value in (og_title, title, meta_description, *visible_parts[:30]):
        cleaned = _clean_product_candidate(value)
        if not cleaned:
            continue
        if cleaned.casefold() not in {item.casefold() for item in candidates}:
            candidates.append(cleaned)
        if len(candidates) >= 5:
            break
    return candidates


def _clean_product_candidate(value: object) -> str | None:
    text = _clean_text(value, max_length=140)
    if not text:
        return None
    text = re.sub(r"[-_｜|]\s*(淘宝网|天猫|京东\(JD\.COM\)|京东|拼多多).*$", "", text, flags=re.IGNORECASE).strip()
    if len(text) < 4 or len(text) > 120:
        return None
    if _looks_blocked(None, text):
        return None
    return text


def _price_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for pattern in (PRICE_CONTEXT_RE, PRICE_RE):
        for match in pattern.finditer(text):
            candidate = _clean_text(match.group(0), max_length=80)
            if not candidate:
                continue
            if candidate.casefold() in {item.casefold() for item in candidates}:
                continue
            candidates.append(candidate)
            if len(candidates) >= 10:
                return candidates
    return candidates


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
