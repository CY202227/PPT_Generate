from ppt_generate.utils.config import Config


def test_user_aliases_and_precedence(monkeypatch):
    for name in [
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL_NAME",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "GENERATOR_MODEL",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("API_KEY", "fake-test-key")
    monkeypatch.setenv("API_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    cfg = Config().generator
    assert cfg.api_key == "fake-test-key"
    assert cfg.base_url == "http://localhost:1234/v1"
    assert cfg.model_name == "test-model"
    monkeypatch.setenv("LLM_MODEL_NAME", "preferred-model")
    assert Config().generator.model_name == "preferred-model"
