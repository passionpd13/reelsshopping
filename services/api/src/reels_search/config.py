from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    serpapi_key: str = ""

    taobao_cookie: str = ""
    alibaba1688_cookie: str = ""
    douyin_cookie: str = ""

    search_platforms: str = "taobao,alibaba1688,douyin"
    max_candidates_per_platform: int = Field(default=8, ge=1, le=30)
    max_results: int = Field(default=3, ge=1, le=10)
    download_dir: Path = Path("./downloads")

    @property
    def platform_list(self) -> list[str]:
        return [p.strip() for p in self.search_platforms.split(",") if p.strip()]


settings = Settings()
