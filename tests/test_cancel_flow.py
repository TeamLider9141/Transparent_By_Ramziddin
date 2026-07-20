from unittest.mock import AsyncMock, MagicMock

import pytest

import transparent


def make_callback_update(user_id=1, data="flow:cancel"):
    update = MagicMock()
    update.callback_query.data = data
    update.callback_query.from_user.id = user_id
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


async def test_cancel_to_action_selection_reuses_stored_photo():
    update = make_callback_update()
    context = MagicMock()
    context.user_data = {"photo": "photos/1.jpg"}

    state = await transparent.cancel_to_action_selection(update, context)

    assert state == transparent.ACTION
    _, kwargs = update.callback_query.edit_message_text.call_args
    markup = kwargs["reply_markup"]
    callback_data_values = [
        button.callback_data for row in markup.inline_keyboard for button in row
    ]
    assert "action:resize" in callback_data_values


async def test_cancel_to_action_selection_ends_if_photo_missing():
    update = make_callback_update()
    context = MagicMock()
    context.user_data = {}

    state = await transparent.cancel_to_action_selection(update, context)

    assert state == transparent.ConversationHandler.END
    update.callback_query.edit_message_text.assert_awaited_once_with(
        "Iltimos, rasmni qaytadan yuboring."
    )


def make_text_update(text):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 1
    return update


async def test_resize_size_invalid_format_includes_cancel_button():
    update = make_text_update("not-a-size")
    context = MagicMock()
    context.user_data = {}

    state = await transparent.resize_size(update, context)

    assert state == transparent.SIZE
    _, kwargs = update.message.reply_text.call_args
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "flow:cancel"


async def test_resize_size_valid_format_prompts_limit_with_cancel_button():
    update = make_text_update("512x512")
    context = MagicMock()
    context.user_data = {}

    state = await transparent.resize_size(update, context)

    assert state == transparent.LIMIT
    _, kwargs = update.message.reply_text.call_args
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "flow:cancel"


async def test_resize_limit_invalid_input_includes_cancel_button():
    update = make_text_update("not-a-number")
    context = MagicMock()
    context.user_data = {}

    state = await transparent.resize_limit(update, context)

    assert state == transparent.LIMIT
    _, kwargs = update.message.reply_text.call_args
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "flow:cancel"
