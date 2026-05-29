from __future__ import annotations

import pytest

from app.services.product_intake.domestic_url_parser import parse_domestic_product_url


def test_taobao_url_parser_extracts_item_id() -> None:
    result = parse_domestic_product_url("https://item.taobao.com/item.htm?id=729576498123&spm=abc")

    assert result.platform == "taobao"
    assert result.item_id == "729576498123"
    assert result.sku_id == ""
    assert result.parse_status == "parsed"
    assert result.normalized_url == "https://item.taobao.com/item.htm?id=729576498123"
    assert "spm" not in result.normalized_url


def test_tmall_url_parser_detects_platform() -> None:
    result = parse_domestic_product_url("https://detail.tmall.com/item.htm?id=735808789012&skuId=188")

    assert result.platform == "tmall"
    assert result.item_id == "735808789012"
    assert result.sku_id == "188"
    assert result.parse_status == "parsed"
    assert result.normalized_url == "https://detail.tmall.com/item.htm?id=735808789012&skuId=188"


def test_jd_url_parser_extracts_sku_id() -> None:
    result = parse_domestic_product_url("https://item.jd.com/100012043978.html?cu=true")

    assert result.platform == "jd"
    assert result.item_id == "100012043978"
    assert result.sku_id == "100012043978"
    assert result.parse_status == "parsed"
    assert result.normalized_url == "https://item.jd.com/100012043978.html"


@pytest.mark.parametrize(
    "url",
    [
        "https://mobile.yangkeduo.com/goods.html?goods_id=1234567890",
        "https://mobile.pinduoduo.com/goods.html?goodsId=1234567890",
    ],
)
def test_pinduoduo_url_parser_recognizes_goods_id(url: str) -> None:
    result = parse_domestic_product_url(url)

    assert result.platform == "pinduoduo"
    assert result.item_id == "1234567890"
    assert result.parse_status == "parsed"
    assert result.normalized_url == "https://mobile.yangkeduo.com/goods.html?goods_id=1234567890"


@pytest.mark.parametrize(
    ("url", "expected_status"),
    [
        ("http://localhost/item", "blocked_host"),
        ("http://127.0.0.1/item", "blocked_host"),
        ("http://10.0.0.2/item", "blocked_host"),
        ("http://172.16.1.2/item", "blocked_host"),
        ("http://192.168.1.2/item", "blocked_host"),
        ("http://169.254.169.254/latest/meta-data", "blocked_host"),
        ("http://100.100.100.200/latest/meta-data", "blocked_host"),
        ("http://[::1]/item", "blocked_host"),
        ("file:///etc/passwd", "invalid_scheme"),
        ("ftp://item.jd.com/100012043978.html", "invalid_scheme"),
        ("https://item.jd.com@127.0.0.1/100012043978.html", "blocked_host"),
        ("https://taobao.com.evil.test/item.htm?id=729576498123", "unsupported_domain"),
    ],
)
def test_url_parser_rejects_private_or_non_http_targets(url: str, expected_status: str) -> None:
    result = parse_domestic_product_url(url)

    assert result.platform == "unknown"
    assert result.parse_status == expected_status
    assert result.normalized_url == ""
