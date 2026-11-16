import json

from app import config, settings_store


def test_saved_key_overrides_env_and_is_masked(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ASR_API_KEY", "")
    assert settings_store.asr()["source"] == "none"

    monkeypatch.setattr(config, "ASR_API_KEY", "env-key-1234567890")
    assert settings_store.asr() == {"base_url": config.ASR_BASE_URL, "api_key": "env-key-1234567890",
                                    "model": config.ASR_MODEL, "source": "env"}

    settings_store.save_asr("openai", "  test-key-abcdefghijklmnop  ")
    cfg = settings_store.asr()
    assert cfg == {"base_url": "https://api.openai.com/v1", "api_key": "test-key-abcdefghijklmnop",
                   "model": "whisper-1", "source": "settings"}
    assert settings_store.provider_of(cfg["base_url"]) == "openai"
    assert settings_store.masked(cfg["api_key"]) == "tes…mnop"
    assert json.loads((tmp_path / "settings.json").read_text())["asr"]["model"] == "whisper-1"

    settings_store.clear_asr()
    assert settings_store.asr()["source"] == "env"


def test_custom_provider_requires_address_and_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    try:
        settings_store.save_asr("custom", "key-123456789012")
    except ValueError:
        pass
    else:
        raise AssertionError("custom provider without base_url/model must be rejected")
    settings_store.save_asr("custom", "key-123456789012", "https://example.test/v1/", "my-whisper")
    assert settings_store.asr()["base_url"] == "https://example.test/v1"
    assert settings_store.provider_of("https://example.test/v1") == "custom"
    assert settings_store.masked("short") == "…"
