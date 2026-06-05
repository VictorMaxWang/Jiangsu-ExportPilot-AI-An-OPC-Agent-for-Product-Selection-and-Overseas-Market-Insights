from __future__ import annotations

from decimal import Decimal


MAX_TARGET_COUNTRIES = 20

DEFAULT_TARGET_COUNTRIES: tuple[str, ...] = ("US", "GB", "JP", "AU", "SG")
TARGET_COUNTRY_CODES: tuple[str, ...] = (
    "JP",
    "KR",
    "SG",
    "MY",
    "AE",
    "GB",
    "DE",
    "FR",
    "NL",
    "IT",
    "US",
    "CA",
    "MX",
    "BR",
    "CL",
    "AU",
    "NZ",
    "ZA",
    "EG",
)

COUNTRY_NAMES_EN: dict[str, str] = {
    "JP": "Japan",
    "KR": "South Korea",
    "SG": "Singapore",
    "MY": "Malaysia",
    "AE": "United Arab Emirates",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "NL": "Netherlands",
    "IT": "Italy",
    "US": "United States",
    "CA": "Canada",
    "MX": "Mexico",
    "BR": "Brazil",
    "CL": "Chile",
    "AU": "Australia",
    "NZ": "New Zealand",
    "ZA": "South Africa",
    "EG": "Egypt",
    "CN": "China",
}

ISO2_TO_ISO3: dict[str, str] = {
    "JP": "JPN",
    "KR": "KOR",
    "SG": "SGP",
    "MY": "MYS",
    "AE": "ARE",
    "GB": "GBR",
    "DE": "DEU",
    "FR": "FRA",
    "NL": "NLD",
    "IT": "ITA",
    "US": "USA",
    "CA": "CAN",
    "MX": "MEX",
    "BR": "BRA",
    "CL": "CHL",
    "AU": "AUS",
    "NZ": "NZL",
    "ZA": "ZAF",
    "EG": "EGY",
    "CN": "CHN",
}

ISO3_TO_ISO2: dict[str, str] = {value: key for key, value in ISO2_TO_ISO3.items()}

UN_COMTRADE_COUNTRY_CODES: dict[str, str] = {
    "JP": "392",
    "KR": "410",
    "SG": "702",
    "MY": "458",
    "AE": "784",
    "GB": "826",
    "DE": "276",
    "FR": "250",
    "NL": "528",
    "IT": "380",
    "US": "842",
    "CA": "124",
    "MX": "484",
    "BR": "76",
    "CL": "152",
    "AU": "36",
    "NZ": "554",
    "ZA": "710",
    "EG": "818",
    "CN": "156",
}

COUNTRY_ALIASES: dict[str, str] = {
    "UK": "GB",
    "UNITED KINGDOM": "GB",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "USA": "US",
    "JAPAN": "JP",
    "SOUTH KOREA": "KR",
    "KOREA": "KR",
    "REPUBLIC OF KOREA": "KR",
    "SINGAPORE": "SG",
    "MALAYSIA": "MY",
    "UNITED ARAB EMIRATES": "AE",
    "UAE": "AE",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "NETHERLANDS": "NL",
    "ITALY": "IT",
    "CANADA": "CA",
    "MEXICO": "MX",
    "BRAZIL": "BR",
    "CHILE": "CL",
    "AUSTRALIA": "AU",
    "NEW ZEALAND": "NZ",
    "SOUTH AFRICA": "ZA",
    "EGYPT": "EG",
    "CHINA": "CN",
    "PEOPLES REPUBLIC OF CHINA": "CN",
}
COUNTRY_ALIASES.update({iso2: iso2 for iso2 in ISO2_TO_ISO3})
COUNTRY_ALIASES.update({iso3: iso2 for iso2, iso3 in ISO2_TO_ISO3.items()})

GDELT_SOURCE_COUNTRIES: dict[str, str] = {
    "JP": "japan",
    "KR": "southkorea",
    "SG": "singapore",
    "MY": "malaysia",
    "AE": "unitedarabemirates",
    "GB": "unitedkingdom",
    "DE": "germany",
    "FR": "france",
    "NL": "netherlands",
    "IT": "italy",
    "US": "unitedstates",
    "CA": "canada",
    "MX": "mexico",
    "BR": "brazil",
    "CL": "chile",
    "AU": "australia",
    "NZ": "newzealand",
    "ZA": "southafrica",
    "EG": "egypt",
    "CN": "china",
}

COUNTRY_CURRENCY: dict[str, str] = {
    "JP": "JPY",
    "KR": "KRW",
    "SG": "SGD",
    "MY": "MYR",
    "AE": "AED",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "NL": "EUR",
    "IT": "EUR",
    "US": "USD",
    "CA": "CAD",
    "MX": "MXN",
    "BR": "BRL",
    "CL": "CLP",
    "AU": "AUD",
    "NZ": "NZD",
    "ZA": "ZAR",
    "EG": "EGP",
}

CNY_TO_TARGET_CURRENCY: dict[str, Decimal] = {
    "USD": Decimal("0.14"),
    "GBP": Decimal("0.11"),
    "EUR": Decimal("0.13"),
    "JPY": Decimal("22.00"),
    "KRW": Decimal("190.00"),
    "SGD": Decimal("0.19"),
    "MYR": Decimal("0.66"),
    "AED": Decimal("0.51"),
    "CAD": Decimal("0.19"),
    "MXN": Decimal("2.55"),
    "BRL": Decimal("0.77"),
    "CLP": Decimal("130.00"),
    "AUD": Decimal("0.21"),
    "NZD": Decimal("0.23"),
    "ZAR": Decimal("2.52"),
    "EGP": Decimal("6.80"),
}

COUNTRY_LOGISTICS_BASE: dict[str, int] = {
    "JP": 90,
    "KR": 85,
    "SG": 90,
    "MY": 72,
    "AE": 80,
    "GB": 70,
    "DE": 82,
    "FR": 78,
    "NL": 86,
    "IT": 72,
    "US": 70,
    "CA": 72,
    "MX": 65,
    "BR": 55,
    "CL": 62,
    "AU": 70,
    "NZ": 68,
    "ZA": 58,
    "EG": 52,
}


def normalize_country_code(value: object, *, allow_name_aliases: bool = False) -> str:
    normalized = str(value or "").strip().upper()
    aliased = COUNTRY_ALIASES.get(normalized)
    if aliased and (allow_name_aliases or (len(normalized) in {2, 3} and normalized.isalpha())):
        return aliased
    if len(normalized) not in {2, 3} or not normalized.isalpha():
        raise ValueError("country code must be a two- or three-letter ISO code")
    return aliased or normalized


def normalize_country_codes(
    values: list[str],
    *,
    field_name: str,
    max_count: int = MAX_TARGET_COUNTRIES,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_country_code(value)
        if normalized not in seen:
            cleaned.append(normalized)
            seen.add(normalized)
    if not cleaned:
        raise ValueError(f"At least one {field_name} entry is required")
    if len(cleaned) > max_count:
        raise ValueError(f"{field_name} supports at most {max_count} unique countries")
    return cleaned
