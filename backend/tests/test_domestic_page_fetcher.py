from __future__ import annotations

import asyncio

import httpx

from app.services.product_intake.domestic_page_fetcher import (
    DomesticPageFetchInput,
    fetch_domestic_product_page,
)


def test_fetcher_blocks_private_dns_resolution_before_request() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, text=_product_html())

    result = asyncio.run(
        fetch_domestic_product_page(
            _fetch_input(),
            transport=httpx.MockTransport(handler),
            resolver=lambda _host, _port: ["127.0.0.1"],
        )
    )

    assert result.parse_status == "needs_screenshot"
    assert result.error_code == "URL_PRIVATE_NETWORK_BLOCKED"
    assert calls == []


def test_fetcher_blocks_redirect_to_private_target() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"})

    result = asyncio.run(
        fetch_domestic_product_page(
            _fetch_input(),
            transport=httpx.MockTransport(handler),
            resolver=lambda _host, _port: ["93.184.216.34"],
        )
    )

    assert result.parse_status == "needs_screenshot"
    assert result.error_code == "URL_PRIVATE_NETWORK_BLOCKED"
    assert calls == ["https://item.jd.com/100012043978.html"]


def test_fetcher_blocks_redirect_to_userinfo_or_disallowed_port() -> None:
    for location in (
        "https://user:item.jd.com@item.jd.com/100012043978.html",
        "https://item.jd.com:444/100012043978.html",
    ):
        calls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(302, headers={"location": location})

        result = asyncio.run(
            fetch_domestic_product_page(
                _fetch_input(),
                transport=httpx.MockTransport(handler),
                resolver=lambda _host, _port: ["93.184.216.34"],
            )
        )

        assert result.parse_status == "needs_screenshot"
        assert result.error_code == "URL_PRIVATE_NETWORK_BLOCKED"
        assert calls == ["https://item.jd.com/100012043978.html"]


def test_fetcher_redirect_limit_returns_needs_screenshot() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://item.jd.com/100012043978.html?next=1"})

    result = asyncio.run(
        fetch_domestic_product_page(
            _fetch_input(),
            transport=httpx.MockTransport(handler),
            resolver=lambda _host, _port: ["93.184.216.34"],
            max_redirects=1,
        )
    )

    assert result.parse_status == "needs_screenshot"
    assert result.error_code == "URL_REDIRECT_LIMIT_EXCEEDED"


def test_fetcher_follows_shortlink_redirect_to_allowed_product_page() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if url.startswith("https://3.cn/"):
            return httpx.Response(302, headers={"location": "https://item.jd.com/100012043978.html"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text=_product_html())

    result = asyncio.run(
        fetch_domestic_product_page(
            DomesticPageFetchInput(
                platform="jd",
                original_url="https://3.cn/-2Q1WvH7?jkl=@X59VX7JUQ1@",
                normalized_url="https://3.cn/-2Q1WvH7?jkl=@X59VX7JUQ1@",
            ),
            transport=httpx.MockTransport(handler),
            resolver=lambda _host, _port: ["93.184.216.34"],
        )
    )

    assert result.parse_status == "parsed"
    assert result.final_url == "https://item.jd.com/100012043978.html"
    assert calls[0].startswith("https://3.cn/-2Q1WvH7?jkl=")
    assert calls[1] == "https://item.jd.com/100012043978.html"


def test_fetcher_sends_no_cookie_or_authorization_headers() -> None:
    seen_headers: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update({key.lower(): value for key, value in request.headers.items()})
        return httpx.Response(200, headers={"content-type": "text/html"}, text=_product_html())

    result = asyncio.run(
        fetch_domestic_product_page(
            _fetch_input(),
            transport=httpx.MockTransport(handler),
            resolver=lambda _host, _port: ["93.184.216.34"],
        )
    )

    assert result.parse_status == "parsed"
    assert "cookie" not in seen_headers
    assert "authorization" not in seen_headers
    assert seen_headers["user-agent"] == "SuPinZhiHangProductIntake/0.1"


def _fetch_input() -> DomesticPageFetchInput:
    return DomesticPageFetchInput(
        platform="jd",
        original_url="https://item.jd.com/100012043978.html",
        normalized_url="https://item.jd.com/100012043978.html",
        item_id="100012043978",
        sku_id="100012043978",
    )


def _product_html() -> str:
    return """
    <html>
      <head>
        <title>宠物凉感垫 - 京东</title>
        <meta name="description" content="夏季宠物凉感垫，参考价￥39.90">
        <meta property="og:title" content="宠物凉感垫">
      </head>
      <body>
        宠物凉感垫 夏季降温 尼龙材质 参考价￥39.90 适合家用宠物护理
      </body>
    </html>
    """
