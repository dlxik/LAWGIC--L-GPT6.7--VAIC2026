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

    # De trong -> SDK tu doc ANTHROPIC_API_KEY tu moi truong
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-4-8"
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
