from unittest.mock import AsyncMock, MagicMock

import pytest

import database
import transparent


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_users.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()
    yield


def make_update(user_id=1, username="alice", first_name="Alice"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.effective_user.first_name = first_name
    update.message.reply_text = AsyncMock()
    return update


async def test_start_records_user_in_db():
    update = make_update(user_id=42, username="bob", first_name="Bob")
    context = MagicMock()

    await transparent.start(update, context)

    assert database.get_user_count() == 1


async def test_start_still_sends_welcome_message():
    update = make_update()
    context = MagicMock()

    await transparent.start(update, context)

    update.message.reply_text.assert_awaited_once()


async def test_start_records_user_with_no_username():
    update = make_update(user_id=7, username=None, first_name="Nobody")
    context = MagicMock()

    await transparent.start(update, context)

    assert database.get_user_count() == 1
