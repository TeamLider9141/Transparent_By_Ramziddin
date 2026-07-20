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


async def test_start_notifies_all_admins_when_new_user(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {111, 222})
    update = make_update(user_id=42, username="bob", first_name="Bob")
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    await transparent.start(update, context)

    assert context.bot.send_message.await_count == 2
    notified_chat_ids = {
        call.kwargs["chat_id"] for call in context.bot.send_message.await_args_list
    }
    assert notified_chat_ids == {111, 222}


async def test_start_does_not_notify_admins_for_returning_user(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {111})
    update = make_update(user_id=42, username="bob", first_name="Bob")
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    await transparent.start(update, context)
    context.bot.send_message.reset_mock()
    await transparent.start(update, context)

    context.bot.send_message.assert_not_awaited()


async def test_start_sends_admin_menu_keyboard_to_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    update = make_update(user_id=1, username="alice", first_name="Alice")
    context = MagicMock()

    await transparent.start(update, context)

    _, kwargs = update.message.reply_text.call_args
    markup = kwargs["reply_markup"]
    labels = [button.text for row in markup.keyboard for button in row]
    assert "👥 Foydalanuvchilar soni" in labels
    assert "📋 Foydalanuvchilar ro'yxati" in labels
    assert "⚙️ Sozlamalar" in labels


async def test_start_sends_start_button_keyboard_to_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    update = make_update(user_id=1, username="alice", first_name="Alice")
    context = MagicMock()

    await transparent.start(update, context)

    _, kwargs = update.message.reply_text.call_args
    markup = kwargs["reply_markup"]
    labels = [button.text for row in markup.keyboard for button in row]
    assert labels == ["🏠 /start"]


async def test_admin_keyboard_is_a_2x2_grid_including_start():
    labels = [[button.text for button in row] for row in transparent.ADMIN_KEYBOARD.keyboard]

    assert labels == [
        ["👥 Foydalanuvchilar soni", "📋 Foydalanuvchilar ro'yxati"],
        ["🏠 /start", "⚙️ Sozlamalar"],
    ]


async def test_start_notifies_remaining_admin_when_one_send_fails(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {111, 222})
    update = make_update(user_id=42, username="bob", first_name="Bob")
    context = MagicMock()
    context.bot.send_message = AsyncMock(
        side_effect=[Exception("bot blocked"), None]
    )

    await transparent.start(update, context)

    assert context.bot.send_message.await_count == 2
    notified_chat_ids = {
        call.kwargs["chat_id"] for call in context.bot.send_message.await_args_list
    }
    assert notified_chat_ids == {111, 222}
