"""Cau hinh tap trung — doc tu .env. KHONG hardcode secret."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = Field(default="lawgic-dev-password")

    # --- LLM. Nha cung cap tuong thich OpenAI (FPT AI Marketplace). ---
    # Doi nha cung cap = doi 3 bien nay, khong dong vao code.
    llm_base_url: str = "https://mkp-api.fptcloud.com"
    llm_api_key: str | None = None
    llm_model: str = "gpt-oss-20b"

    # Giu lai cho tuong thich nguoc. KHONG con duoc doc o dau.
    anthropic_api_key: str | None = None
    llm_effort: str = "high"

    raw_legal_dir: Path = ROOT / "data" / "raw" / "legal_docs"
    raw_posts_dir: Path = ROOT / "data" / "raw" / "social_posts"
    structured_legal_dir: Path = ROOT / "data" / "processed" / "legal_docs_structured"
    labeled_posts_dir: Path = ROOT / "data" / "processed" / "posts_labeled"
    prompts_dir: Path = ROOT / "prompts"

    trend_min_occurrences: int = 5
    trend_window_hours: int = 48


@lru_cache
def get_settings() -> Settings:
    return Settings()
