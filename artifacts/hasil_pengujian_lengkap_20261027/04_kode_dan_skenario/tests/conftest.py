import pytest


@pytest.fixture(autouse=True)
def isolated_chat_storage(tmp_path, monkeypatch):
    """App tests must never read or overwrite the owner's actual conversations."""
    monkeypatch.setenv("DAPURIA_HISTORY_PATH", str(tmp_path / "history.sqlite3"))
