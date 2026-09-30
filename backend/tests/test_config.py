from pathlib import Path

import pytest

from review_radar.config import DEFAULT_OPENAI_EMBEDDINGS, DEFAULT_OPENAI_MODEL, Settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for key in ("MODEL", "EMBEDDING_MODEL", "OPENAI_API_KEY", "POSTING_ENABLED", "CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)


def test_demo_by_default_and_empty_values_are_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTING_ENABLED", "")
    monkeypatch.setenv("MODEL", "")
    settings = Settings()
    assert settings.demo_mode
    assert settings.resolved_embedding_model == "demo"
    assert settings.posting_enabled is False


def test_openai_key_switches_to_real_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    settings = Settings()
    assert settings.resolved_model == DEFAULT_OPENAI_MODEL
    assert settings.resolved_embedding_model == DEFAULT_OPENAI_EMBEDDINGS
    assert "sk-test" not in repr(settings)


def test_other_provider_keeps_offline_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "anthropic:some-model")
    assert Settings().resolved_embedding_model == "demo"


def test_cors_origins_from_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings().cors_origins == ["https://a.example", "https://b.example"]


def test_store_configuration_flags(tmp_path: Path) -> None:
    key = tmp_path / "key.p8"
    key.write_text("pem")
    settings = Settings(
        app_store_app_id="1",
        app_store_issuer_id="i",
        app_store_key_id="k",
        app_store_private_key_path=key,
        google_play_package_name="app.pp",
        google_play_service_account_file=tmp_path / "sa.json",
    )
    assert settings.app_store_configured
    assert settings.app_store_key_pem() == "pem"
    assert settings.google_play_configured
    assert not Settings().app_store_configured
    assert Settings().app_store_key_pem() is None
