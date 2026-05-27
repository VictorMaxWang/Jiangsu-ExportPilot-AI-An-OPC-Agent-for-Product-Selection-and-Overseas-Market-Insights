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

    @field_validator("bailian_api_key", mode="before")
    @classmethod
    def _empty_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    model_config = SettingsConfigDict(env_prefix="SUPIN_", extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
