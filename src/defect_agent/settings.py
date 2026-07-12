from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """전역 설정 — .env에서 로드한다 (설정 외부화 원칙)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"
    data_dir: Path = Path("data")
    stores_dir: Path = Path("stores")  # V1·V2·D1 저장소 루트 — 차단 검사의 스캔 대상
