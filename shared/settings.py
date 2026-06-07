import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

RESERVED_PORTS = frozenset({1213, 8000, 12345})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8765, alias="PORT")
    brave_api_key: str | None = Field(default=None, alias="BRAVE_API_KEY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    http_timeout: int = Field(default=20, alias="HTTP_TIMEOUT")
    browser_timeout: int = Field(default=30, alias="BROWSER_TIMEOUT")
    browser_headless: bool = Field(default=True, alias="BROWSER_HEADLESS")
    search_provider: str = Field(default="auto", alias="SEARCH_PROVIDER")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    local_file_root: str | None = Field(default=None, alias="LOCAL_FILE_ROOT")
    allowlist_domains: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="ALLOWLIST_DOMAINS"
    )

    @field_validator("allowlist_domains", mode="before")
    @classmethod
    def parse_allowlist_domains(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("ALLOWLIST_DOMAINS JSON value must be a list")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("port")
    @classmethod
    def validate_reserved_port(cls, value: int) -> int:
        if value in RESERVED_PORTS:
            reserved = ", ".join(str(port) for port in sorted(RESERVED_PORTS))
            raise ValueError(f"PORT {value} is reserved and cannot be used; blocked ports: {reserved}")
        return value

    @field_validator("search_provider")
    @classmethod
    def validate_search_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"auto", "brave", "ddgs"}
        if normalized not in allowed:
            raise ValueError(f"SEARCH_PROVIDER must be one of: {', '.join(sorted(allowed))}")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
