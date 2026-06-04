from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "SuPin ZhiHang Backend"
    project_version: str = "0.1.0"
    app_env: str = Field(
        default="local",
        validation_alias=AliasChoices("APP_ENV", "SUPIN_APP_ENV"),
    )
    database_url: str = Field(
        default="sqlite:///./supinzhihang.db",
        validation_alias=AliasChoices("DATABASE_URL", "SUPIN_DATABASE_URL"),
    )
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ORIGINS", "SUPIN_CORS_ORIGINS"),
    )
    public_site_origin: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_SITE_ORIGIN", "SUPIN_PUBLIC_SITE_ORIGIN"),
    )
    allowed_admin_origins: str = Field(
        default="",
        validation_alias=AliasChoices("ALLOWED_ADMIN_ORIGINS", "SUPIN_ALLOWED_ADMIN_ORIGINS"),
    )
    admin_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_PASSWORD", "SUPIN_ADMIN_PASSWORD"),
    )
    admin_auth_enabled: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_AUTH_ENABLED", "SUPIN_ADMIN_AUTH_ENABLED"),
    )
    bailian_api_key: str | None = Field(
        default=None,
        validation_alias="DASHSCOPE_API_KEY",
    )
    bailian_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("BAILIAN_BASE_URL", "SUPIN_BAILIAN_BASE_URL"),
    )
    bailian_model: str = Field(
        default="qwen3.6-plus",
        validation_alias=AliasChoices("BAILIAN_MODEL", "SUPIN_BAILIAN_MODEL"),
    )
    bailian_vision_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BAILIAN_VISION_ENABLED", "SUPIN_BAILIAN_VISION_ENABLED"),
    )
    bailian_vision_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BAILIAN_VISION_MODEL", "SUPIN_BAILIAN_VISION_MODEL"),
    )
    bailian_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        validation_alias=AliasChoices("BAILIAN_TIMEOUT_SECONDS", "SUPIN_BAILIAN_TIMEOUT_SECONDS"),
    )
    bailian_max_retries: int = Field(
        default=2,
        ge=0,
        validation_alias=AliasChoices("BAILIAN_MAX_RETRIES", "SUPIN_BAILIAN_MAX_RETRIES"),
    )
    product_upload_dir: str = Field(
        default="storage/product-intake",
        validation_alias=AliasChoices("PRODUCT_UPLOAD_DIR", "SUPIN_PRODUCT_UPLOAD_DIR"),
    )
    max_product_image_size_mb: float = Field(
        default=10.0,
        gt=0,
        validation_alias=AliasChoices("MAX_PRODUCT_IMAGE_SIZE_MB", "SUPIN_MAX_PRODUCT_IMAGE_SIZE_MB"),
    )
    enable_domestic_url_fetch: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_DOMESTIC_URL_FETCH", "SUPIN_ENABLE_DOMESTIC_URL_FETCH"),
    )
    youtube_data_api_key: str | None = Field(
        default=None,
        validation_alias="YOUTUBE_DATA_API_KEY",
    )
    enable_youtube: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_YOUTUBE", "SUPIN_ENABLE_YOUTUBE"),
    )
    etsy_keystring: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ETSY_KEYSTRING", "SUPIN_ETSY_KEYSTRING"),
    )
    etsy_shared_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ETSY_SHARED_SECRET", "SUPIN_ETSY_SHARED_SECRET"),
    )
    enable_etsy: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_ETSY", "SUPIN_ENABLE_ETSY"),
    )
    un_comtrade_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("UN_COMTRADE_API_KEY", "SUPIN_UN_COMTRADE_API_KEY"),
    )
    enable_un_comtrade: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_UN_COMTRADE", "SUPIN_ENABLE_UN_COMTRADE"),
    )
    data_collection_concurrency: int = Field(
        default=3,
        ge=1,
        le=8,
        validation_alias=AliasChoices("DATA_COLLECTION_CONCURRENCY", "SUPIN_DATA_COLLECTION_CONCURRENCY"),
    )
    ebay_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EBAY_CLIENT_ID", "SUPIN_EBAY_CLIENT_ID"),
    )
    ebay_client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EBAY_CLIENT_SECRET", "SUPIN_EBAY_CLIENT_SECRET"),
    )
    rakuten_app_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RAKUTEN_APP_ID",
            "RAKUTEN_APPLICATION_ID",
            "SUPIN_RAKUTEN_APP_ID",
            "SUPIN_RAKUTEN_APPLICATION_ID",
        ),
    )
    reddit_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDDIT_CLIENT_ID", "SUPIN_REDDIT_CLIENT_ID"),
    )
    reddit_client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDDIT_CLIENT_SECRET", "SUPIN_REDDIT_CLIENT_SECRET"),
    )

    @field_validator(
        "bailian_api_key",
        "youtube_data_api_key",
        "etsy_keystring",
        "etsy_shared_secret",
        "un_comtrade_api_key",
        "ebay_client_id",
        "ebay_client_secret",
        "rakuten_app_id",
        "reddit_client_id",
        "reddit_client_secret",
        "admin_password",
        "public_site_origin",
        "admin_auth_enabled",
        "bailian_vision_model",
        mode="before",
    )
    @classmethod
    def _empty_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    model_config = SettingsConfigDict(env_prefix="SUPIN_", extra="ignore", populate_by_name=True)

    def cors_origin_list(self) -> list[str]:
        origins = _split_origins(self.cors_origins)
        if self.is_production():
            origins = [origin for origin in origins if _is_production_origin(origin)]
            if self.public_site_origin:
                origins.append(self.public_site_origin)
            origins.extend(_split_origins(self.allowed_admin_origins))
            origins = [origin for origin in origins if _is_production_origin(origin)]
        return _dedupe_origins(origins)

    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def is_admin_auth_enabled(self) -> bool:
        if self.admin_auth_enabled is not None:
            return self.admin_auth_enabled
        return self.is_production()


def _split_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _dedupe_origins(origins: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for origin in origins:
        if origin not in seen:
            seen.add(origin)
            deduped.append(origin)
    return deduped


def _is_production_origin(origin: str) -> bool:
    return origin.startswith("https://") and origin != "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
