import pytest

from jobscout import db


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("JOBSCOUT_DB", str(path))
    return str(path)


@pytest.fixture()
def conn(db_path):
    c = db.connect(db_path)
    yield c
    c.close()
