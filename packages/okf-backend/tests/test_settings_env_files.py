"""BackendSettings reads ``./.env`` and falls back to ``<OKF_HOME>/.env``."""

import pytest

from okf_backend.settings import BackendSettings

_KEYS = ("OKF_EMBEDDING_URL", "OKF_EMBEDDING_MODEL", "OKF_EMBEDDING_API_KEY",
         "OKF_EMBEDDING_MAX_CHARS")


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setenv("OKF_HOME", str(home))
    monkeypatch.chdir(cwd)
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)
    return home, cwd


def test_reads_okf_home_env_file(dirs):
    home, _ = dirs
    (home / ".env").write_text("OKF_EMBEDDING_URL=http://home/v1\nOKF_EMBEDDING_MODEL=m\n")
    cfg = BackendSettings().embedding_config()
    assert (cfg.url, cfg.model) == ("http://home/v1", "m")


def test_cwd_env_file_wins_over_okf_home(dirs):
    home, cwd = dirs
    (home / ".env").write_text("OKF_EMBEDDING_URL=http://home/v1\nOKF_EMBEDDING_MODEL=m\n")
    (cwd / ".env").write_text("OKF_EMBEDDING_URL=http://cwd/v1\n")
    cfg = BackendSettings().embedding_config()
    assert (cfg.url, cfg.model) == ("http://cwd/v1", "m")


def test_real_env_wins_over_env_files(dirs, monkeypatch):
    home, cwd = dirs
    (home / ".env").write_text("OKF_EMBEDDING_URL=http://home/v1\nOKF_EMBEDDING_MODEL=m\n")
    (cwd / ".env").write_text("OKF_EMBEDDING_URL=http://cwd/v1\n")
    monkeypatch.setenv("OKF_EMBEDDING_URL", "http://real/v1")
    assert BackendSettings().embedding_url == "http://real/v1"


def test_no_env_files_disables_search(dirs):
    assert BackendSettings().embedding_config() is None


def test_explicit_none_skips_env_files(dirs):
    home, _ = dirs
    (home / ".env").write_text("OKF_EMBEDDING_URL=http://home/v1\nOKF_EMBEDDING_MODEL=m\n")
    assert BackendSettings(_env_file=None).embedding_config() is None
