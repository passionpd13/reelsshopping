from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    data_dir: Path = Field(default=Path("./data"))
    db_url: str = "sqlite:///./db.sqlite"

    # LLM provider: "anthropic" (direct API) | "vertex" (Google Cloud Vertex AI)
    llm_provider: str = "anthropic"

    # Anthropic direct API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Vertex AI (Google Cloud) — used when llm_provider=vertex
    vertex_project_id: str = ""
    vertex_region: str = "us-east5"
    vertex_model: str = "claude-sonnet-4-5@20250929"
    google_application_credentials: str = ""

    supertone_api_key: str = ""
    supertone_base_url: str = "https://supertoneapi.com"
    supertone_default_voice_id: str = ""

    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    ytdlp_cookies_file: str = ""

    render_width: int = 1080
    render_height: int = 1920
    render_fps: int = 30

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def transcripts_dir(self) -> Path:
        return self.data_dir / "transcripts"

    @property
    def scenes_dir(self) -> Path:
        return self.data_dir / "scenes"

    @property
    def tts_dir(self) -> Path:
        return self.data_dir / "tts"

    @property
    def renders_dir(self) -> Path:
        return self.data_dir / "renders"

    @property
    def products_dir(self) -> Path:
        return self.data_dir / "products"

    def ensure_dirs(self) -> None:
        for p in (
            self.sources_dir,
            self.transcripts_dir,
            self.scenes_dir,
            self.tts_dir,
            self.renders_dir,
            self.products_dir,
        ):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
