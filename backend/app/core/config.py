from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "SuPin ZhiHang Backend"
    project_version: str = "0.1.0"
    database_url: str = Field(
        default="sqlite:///./supinzhihang.db",
        validation_alias=AliasChoices("DATABASE_URL", "SUPIN_DATABASE_URL"),
    )
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ORIGINS", "SUPIN_CORS_ORIGINS"),
    )
    bailian_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "DASHSCOPE_API_KEY",
            "BAILIAN_API_KEY",
            "SUPIN_DASHSCOPE_API_KEY",
            "SUPIN_BAILIAN_API_KEY",
        ),
    )
    bailian_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("BAILIAN_BASE_URL", "SUPIN_BAILIAN_BASE_URL"),
    )
    bailian_model: str = Field(
        default="qwen3.6-plus",
        validation_alias=AliasChoices("BAILIAN_MODEL", "SUPIN_BAILIAN_MODEL"),
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
        mode="before",
    )
    @classmethod
    def _empty_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    model_config = SettingsConfigDict(env_prefix="SUPIN_", extra="ignore", populate_by_name=True)

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
