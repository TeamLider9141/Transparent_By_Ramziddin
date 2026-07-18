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


def make_command_update(user_id):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    return update


def make_callback_update(user_id, data):
    update = MagicMock()
    update.callback_query.from_user.id = user_id
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


async def test_userlist_cmd_denies_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    update = make_command_update(user_id=1)

    await transparent.userlist_cmd(update, MagicMock())

    update.message.reply_text.assert_awaited_once_with("⛔ Bu buyruq faqat admin uchun.")


async def test_userlist_cmd_shows_first_page(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    database.add_user(10, "alice", "Alice")
    update = make_command_update(user_id=1)

    await transparent.userlist_cmd(update, MagicMock())

    args, kwargs = update.message.reply_text.call_args
    assert "10" in args[0]
    assert "alice" in args[0]
    assert kwargs.get("reply_markup") is None  # only one user, no next page


async def test_userlist_cmd_shows_next_button_when_more_rows_exist(monkeypatch):
    monkeypatch.setattr(transparent, "PAGE_SIZE", 1)
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    database.add_user(10, "alice", "Alice")
    database.add_user(11, "bob", "Bob")
    update = make_command_update(user_id=1)

    await transparent.userlist_cmd(update, MagicMock())

    _, kwargs = update.message.reply_text.call_args
    markup = kwargs["reply_markup"]
    buttons = [b.text for row in markup.inline_keyboard for b in row]
    assert "Keyingi ➡️" in buttons
    assert "⬅️ Oldinga" not in buttons


async def test_userlist_callback_ignores_non_admin():
    update = make_callback_update(user_id=999, data="userlist:0")

    await transparent.userlist_callback(update, MagicMock())

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_not_called()


async def test_userlist_callback_edits_message_for_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    database.add_user(10, "alice", "Alice")
    update = make_callback_update(user_id=1, data="userlist:0")

    await transparent.userlist_callback(update, MagicMock())

    update.callback_query.edit_message_text.assert_awaited_once()
