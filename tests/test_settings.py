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


async def test_settings_cmd_denies_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    update = make_command_update(user_id=1)

    await transparent.settings_cmd(update, MagicMock())

    update.message.reply_text.assert_awaited_once_with("⛔ Bu buyruq faqat admin uchun.")


async def test_settings_cmd_shows_panel_for_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    update = make_command_update(user_id=1)

    await transparent.settings_cmd(update, MagicMock())

    args, kwargs = update.message.reply_text.call_args
    buttons = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "📊 Statistika" in buttons
    assert "👥 Foydalanuvchilar ro'yxati" in buttons


async def test_settings_callback_stats_shows_counts(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    database.add_user(10, "alice", "Alice")
    update = make_callback_update(user_id=1, data="settings:stats")

    await transparent.settings_callback(update, MagicMock())

    args, _ = update.callback_query.edit_message_text.call_args
    assert "Jami: 1" in args[0]
    assert "Bugun: 1" in args[0]


async def test_settings_callback_userlist_shows_page(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    database.add_user(10, "alice", "Alice")
    update = make_callback_update(user_id=1, data="settings:userlist")

    await transparent.settings_callback(update, MagicMock())

    args, _ = update.callback_query.edit_message_text.call_args
    assert "alice" in args[0]


async def test_settings_callback_denies_non_admin():
    update = make_callback_update(user_id=999, data="settings:stats")

    await transparent.settings_callback(update, MagicMock())

    update.callback_query.edit_message_text.assert_not_called()
