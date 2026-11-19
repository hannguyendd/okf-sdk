def test_backend_exports():
    from okf_backend import operations
    from okf_backend.embeddings import EmbeddingConfig
    from okf_backend.settings import BackendSettings
    assert callable(operations.add_concept)
    assert BackendSettings(_env_file=None).embedding_config() is None

def test_backend_settings_builds_config(monkeypatch):
    from okf_backend.settings import BackendSettings
    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://h/v1")
    monkeypatch.setenv("OKF_EMBEDDING_MODEL", "m")
    cfg = BackendSettings(_env_file=None).embedding_config()
    assert (cfg.url, cfg.model) == ("http://h/v1", "m")
