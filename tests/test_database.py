import importlib

import pytest

import database


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_users.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()
    yield


def test_init_db_creates_empty_table():
    assert database.get_user_count() == 0


def test_add_user_inserts_row():
    database.add_user(1, "alice", "Alice")
    assert database.get_user_count() == 1


def test_add_user_is_idempotent_per_user_id():
    database.add_user(1, "alice", "Alice")
    database.add_user(1, "alice", "Alice")
    assert database.get_user_count() == 1


def test_add_user_returns_true_when_new_user_inserted():
    assert database.add_user(1, "alice", "Alice") is True


def test_add_user_returns_false_when_user_already_exists():
    database.add_user(1, "alice", "Alice")
    assert database.add_user(1, "alice", "Alice") is False


def test_get_today_count_counts_only_todays_users():
    database.add_user(1, "alice", "Alice")
    assert database.get_today_count() == 1


def test_get_users_page_orders_newest_first_and_respects_limit():
    database.add_user(1, "alice", "Alice")
    database.add_user(2, "bob", "Bob")
    database.add_user(3, "carol", "Carol")

    page = database.get_users_page(offset=0, limit=2)

    assert len(page) == 2
    assert [row[0] for row in page] == [3, 2]


def test_get_users_page_offset_returns_remaining_rows():
    database.add_user(1, "alice", "Alice")
    database.add_user(2, "bob", "Bob")
    database.add_user(3, "carol", "Carol")

    page = database.get_users_page(offset=2, limit=2)

    assert [row[0] for row in page] == [1]
