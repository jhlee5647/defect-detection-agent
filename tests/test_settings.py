from pathlib import Path

from defect_agent.settings import Settings


def test_기본값_로드(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "LLM_MODEL", "DATA_DIR"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)
    assert s.llm_model == "claude-opus-4-8"
    assert s.data_dir == Path("data")


def test_환경변수_우선(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    s = Settings(_env_file=None)
    assert s.llm_model == "claude-sonnet-5"
