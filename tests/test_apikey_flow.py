from unittest.mock import AsyncMock, MagicMock

import pytest

import transparent


def make_callback_update(user_id, data):
    update = MagicMock()
    update.callback_query.data = data
    update.callback_query.from_user.id = user_id
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def make_text_update(user_id, text):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.delete = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


# ---------- settings panel button ----------

async def test_settings_panel_includes_apikey_button(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    update = MagicMock()
    update.effective_user.id = 1
    update.message.reply_text = AsyncMock()

    await transparent.settings_cmd(update, MagicMock())

    _, kwargs = update.message.reply_text.call_args
    callback_data = [b.callback_data for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "settings:apikey" in callback_data


# ---------- apikey_start ----------

async def test_apikey_start_admin_prompts_and_returns_await(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    update = make_callback_update(user_id=1, data="settings:apikey")

    state = await transparent.apikey_start(update, MagicMock())

    assert state == transparent.AWAIT_API_KEY
    update.callback_query.edit_message_text.assert_awaited_once()


async def test_apikey_start_denies_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    update = make_callback_update(user_id=1, data="settings:apikey")

    state = await transparent.apikey_start(update, MagicMock())

    assert state == transparent.ConversationHandler.END
    update.callback_query.edit_message_text.assert_not_called()


# ---------- apikey_receive ----------

async def test_apikey_receive_deletes_message(monkeypatch):
    monkeypatch.setattr(transparent, "_validate_remove_bg_key", lambda k: "valid")
    update = make_text_update(user_id=1, text="somekey12345")
    context = MagicMock()
    context.user_data = {}

    await transparent.apikey_receive(update, context)

    update.message.delete.assert_awaited_once()


async def test_apikey_receive_deletes_message_before_validation(monkeypatch):
    # Security: the plaintext key message must be removed from chat history
    # BEFORE the ~15s network validation, not after — otherwise it lingers
    # visible during the round-trip.
    order = []
    update = make_text_update(user_id=1, text="somekey12345")
    update.message.delete = AsyncMock(side_effect=lambda: order.append("delete"))

    def validate(_key):
        order.append("validate")
        return "valid"

    monkeypatch.setattr(transparent, "_validate_remove_bg_key", validate)
    context = MagicMock()
    context.user_data = {}

    await transparent.apikey_receive(update, context)

    assert order == ["delete", "validate"]


async def test_apikey_receive_valid_stores_pending_and_confirms(monkeypatch):
    monkeypatch.setattr(transparent, "_validate_remove_bg_key", lambda k: "valid")
    update = make_text_update(user_id=1, text="uwfYNenrqyEbw6VBCw6wF5Ep")
    context = MagicMock()
    context.user_data = {}

    state = await transparent.apikey_receive(update, context)

    assert state == transparent.CONFIRM_API_KEY
    assert context.user_data["pending_api_key"] == "uwfYNenrqyEbw6VBCw6wF5Ep"
    _, kwargs = update.message.reply_text.call_args
    callback_data = [b.callback_data for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "apikey:save" in callback_data
    assert "apikey:cancel" in callback_data
    # masked key shown, raw key NOT shown in full
    shown = update.message.reply_text.call_args[0][0]
    assert "uwfY...F5Ep" in shown
    assert "uwfYNenrqyEbw6VBCw6wF5Ep" not in shown


async def test_apikey_receive_empty_stays_await(monkeypatch):
    update = make_text_update(user_id=1, text="   ")
    context = MagicMock()
    context.user_data = {}

    state = await transparent.apikey_receive(update, context)

    assert state == transparent.AWAIT_API_KEY
    assert "pending_api_key" not in context.user_data


async def test_apikey_receive_invalid_stays_await(monkeypatch):
    monkeypatch.setattr(transparent, "_validate_remove_bg_key", lambda k: "invalid")
    update = make_text_update(user_id=1, text="badkey12345")
    context = MagicMock()
    context.user_data = {}

    state = await transparent.apikey_receive(update, context)

    assert state == transparent.AWAIT_API_KEY
    assert "pending_api_key" not in context.user_data


async def test_apikey_receive_network_error_stays_await(monkeypatch):
    monkeypatch.setattr(transparent, "_validate_remove_bg_key", lambda k: "error")
    update = make_text_update(user_id=1, text="somekey12345")
    context = MagicMock()
    context.user_data = {}

    state = await transparent.apikey_receive(update, context)

    assert state == transparent.AWAIT_API_KEY
    assert "pending_api_key" not in context.user_data
    # error message is distinct from the invalid-key message
    shown = update.message.reply_text.call_args[0][0]
    assert "bog'lan" in shown.lower() or "ulan" in shown.lower()


# ---------- apikey_save ----------

async def test_apikey_save_writes_env_and_updates_global(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    monkeypatch.setattr(transparent, "REMOVE_BG_API", "oldkey")
    written = {}
    monkeypatch.setattr(
        transparent, "_write_env_value",
        lambda k, v, **kw: written.update({k: v}),
    )
    update = make_callback_update(user_id=1, data="apikey:save")
    context = MagicMock()
    context.user_data = {"pending_api_key": "newkey123"}

    state = await transparent.apikey_save(update, context)

    assert state == transparent.ConversationHandler.END
    assert written == {"REMOVE_BG_API": "newkey123"}
    assert transparent.REMOVE_BG_API == "newkey123"
    assert "pending_api_key" not in context.user_data


async def test_apikey_save_write_failure_keeps_old_global(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    monkeypatch.setattr(transparent, "REMOVE_BG_API", "oldkey")

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(transparent, "_write_env_value", boom)

    update = make_callback_update(user_id=1, data="apikey:save")
    context = MagicMock()
    context.user_data = {"pending_api_key": "newkey123"}

    state = await transparent.apikey_save(update, context)

    assert state == transparent.ConversationHandler.END
    # global NOT changed because the write failed
    assert transparent.REMOVE_BG_API == "oldkey"


async def test_apikey_save_denies_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    monkeypatch.setattr(transparent, "REMOVE_BG_API", "oldkey")
    called = {"wrote": False}
    monkeypatch.setattr(transparent, "_write_env_value", lambda *a, **k: called.update(wrote=True))
    update = make_callback_update(user_id=1, data="apikey:save")
    context = MagicMock()
    context.user_data = {"pending_api_key": "newkey123"}

    await transparent.apikey_save(update, context)

    assert called["wrote"] is False
    assert transparent.REMOVE_BG_API == "oldkey"


# ---------- apikey_cancel ----------

async def test_apikey_cancel_discards_pending(monkeypatch):
    monkeypatch.setattr(transparent, "REMOVE_BG_API", "oldkey")
    update = make_callback_update(user_id=1, data="apikey:cancel")
    context = MagicMock()
    context.user_data = {"pending_api_key": "newkey123"}

    state = await transparent.apikey_cancel(update, context)

    assert state == transparent.ConversationHandler.END
    assert "pending_api_key" not in context.user_data
    assert transparent.REMOVE_BG_API == "oldkey"
