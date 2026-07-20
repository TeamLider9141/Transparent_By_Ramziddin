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


def make_photo_update(user_id=1):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = 555
    telegram_file = MagicMock()
    telegram_file.download_to_drive = AsyncMock()
    photo_size = MagicMock()
    photo_size.get_file = AsyncMock(return_value=telegram_file)
    update.message.photo = [photo_size]
    update.message.reply_text = AsyncMock()
    return update


def make_callback_update(user_id, data):
    update = MagicMock()
    update.callback_query.data = data
    update.callback_query.from_user.id = user_id
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message.reply_document = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    return update


async def test_get_photo_sends_inline_action_buttons():
    update = make_photo_update(user_id=1)
    context = MagicMock()
    context.user_data = {}

    state = await transparent.get_photo(update, context)

    assert state == transparent.ACTION
    _, kwargs = update.message.reply_text.call_args
    markup = kwargs["reply_markup"]
    callback_data_values = [
        button.callback_data for row in markup.inline_keyboard for button in row
    ]
    assert callback_data_values == [
        "action:resize",
        "action:transparent",
        "action:both",
        "flow:cancel",
    ]


async def test_get_photo_stores_photo_path_in_user_data():
    update = make_photo_update(user_id=7)
    context = MagicMock()
    context.user_data = {}

    await transparent.get_photo(update, context)

    assert context.user_data["photo"] == "photos/7.jpg"


async def test_action_callback_resize_asks_for_size_with_cancel_button():
    update = make_callback_update(user_id=1, data="action:resize")
    context = MagicMock()
    context.user_data = {"photo": "photos/1.jpg"}

    state = await transparent.action_callback(update, context)

    assert state == transparent.SIZE
    assert context.user_data["mode"] == "resize"
    _, kwargs = update.callback_query.edit_message_text.call_args
    markup = kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == "flow:cancel"


async def test_action_callback_both_asks_for_size():
    update = make_callback_update(user_id=1, data="action:both")
    context = MagicMock()
    context.user_data = {"photo": "photos/1.jpg"}

    state = await transparent.action_callback(update, context)

    assert state == transparent.SIZE
    assert context.user_data["mode"] == "both"
    _, kwargs = update.callback_query.edit_message_text.call_args
    markup = kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == "flow:cancel"


async def test_action_callback_transparent_processes_and_sends_document(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "photos").mkdir()
    input_file = tmp_path / "photos" / "1.jpg"
    input_file.write_bytes(b"fake")
    output_file = tmp_path / "photos" / "1_transparent.png"
    output_file.write_bytes(b"fake-png")
    monkeypatch.setattr(transparent, "remove_background", lambda inp, out: True)

    update = make_callback_update(user_id=1, data="action:transparent")
    context = MagicMock()
    context.user_data = {"photo": str(input_file)}

    state = await transparent.action_callback(update, context)

    assert state == transparent.ConversationHandler.END
    update.callback_query.message.reply_document.assert_awaited_once()


async def test_action_callback_transparent_reports_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "photos").mkdir()
    input_file = tmp_path / "photos" / "1.jpg"
    input_file.write_bytes(b"fake")
    monkeypatch.setattr(transparent, "remove_background", lambda inp, out: False)

    update = make_callback_update(user_id=1, data="action:transparent")
    context = MagicMock()
    context.user_data = {"photo": str(input_file)}

    state = await transparent.action_callback(update, context)

    assert state == transparent.ConversationHandler.END
    update.callback_query.message.reply_text.assert_awaited_once_with(
        "❌ Fon olib tashlashda xatolik yuz berdi."
    )


async def test_action_callback_cancel_ends_conversation():
    update = make_callback_update(user_id=1, data="flow:cancel")
    context = MagicMock()
    context.user_data = {"photo": "photos/1.jpg"}

    state = await transparent.action_callback(update, context)

    assert state == transparent.ConversationHandler.END
    update.callback_query.edit_message_text.assert_awaited_once_with(
        "❌ Jarayon bekor qilindi. Yangi rasm yuboring."
    )
