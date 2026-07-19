# Inline Photo-Flow Buttons + /start Keyboard Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the photo-processing flow's text-based "type 1/2/3" step with inline buttons, add a "❌ Bekor qilish" button available at every step (full-cancel at the action-selection step, "go back to action selection without re-uploading the photo" at the size/limit steps), and add a "🏠 /start" button to the persistent reply keyboard for both admins and regular users.

**Architecture:** `transparent.py`'s `ConversationHandler` (`conv`) gets its `ACTION` state's handler swapped from a text `MessageHandler` to a `CallbackQueryHandler` driven by `callback_data` values (`action:resize`, `action:transparent`, `action:both`, `flow:cancel`). The `SIZE`/`LIMIT` states keep their existing text-input `MessageHandler`s but gain an additional `CallbackQueryHandler` for `flow:cancel` that routes back to the action-selection step by re-using the already-downloaded photo path stored in `context.user_data["photo"]`. The admin/user reply keyboards (`ADMIN_KEYBOARD`, new `USER_KEYBOARD`) both gain a `"🏠 /start"` button wired to the existing `start` handler.

**Tech Stack:** python-telegram-bot 22.x (`InlineKeyboardMarkup`, `CallbackQueryHandler`, `ConversationHandler`), pytest + pytest-asyncio (already configured via `pytest.ini`).

---

## Task 1: Convert photo action-selection to inline buttons, with full-cancel

**Files:**
- Modify: `transparent.py` (`get_photo`, `action` → `action_callback`, `conv`'s `ACTION` state entry)
- Test: `tests/test_photo_flow.py` (new)

**Current state of the relevant code** (verify by reading `transparent.py` yourself first — line numbers may have shifted slightly, but this is the code as of the last commit on `main`):

```python
# ==========================
# RASM QABUL QILISH (Gruppa + Private uchun yangilandi)
# ==========================
async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()
    user_id = update.effective_user.id
    path = f"photos/{user_id}.jpg"
    
    await file.download_to_drive(path)
    context.user_data["photo"] = path
    context.user_data["chat_id"] = update.effective_chat.id  # Guruh yoki private chatni saqlash

    await update.message.reply_text(
        "Rasm qabul qilindi ✅\n\n"
        "Nima qilamiz?\n\n"
        "1 - O'lchamni o'zgartirish\n"
        "2 - Fonni transparent qilish\n"
        "3 - Ikkalasini ham (Fon + O'lcham)\n\n"
        "1, 2 yoki 3 yozing."
    )
    return ACTION
# ==========================
# ACTION TANLASH
# ==========================
async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "1":
        await update.message.reply_text(
            "O'lchamni kiriting (width x height).\n\n"
            "Misol:\n512x512"
        )
        context.user_data["mode"] = "resize"
        return SIZE
        
    elif text == "2":
        await update.message.reply_text("⏳ Fon olib tashlanmoqda...")
        input_file = context.user_data["photo"]
        output_file = f"photos/{update.effective_user.id}_transparent.png"
        
        result = remove_background(input_file, output_file)
        
        if result:
            await update.message.reply_document(
                document=open(output_file, "rb"),
                filename="transparent.png",
                caption="✅ Fon transparent qilindi."
            )
        else:
            await update.message.reply_text("❌ Fon olib tashlashda xatolik yuz berdi.")
        return ConversationHandler.END
        
    elif text == "3":
        await update.message.reply_text(
            "O'lchamni kiriting (width x height).\n\n"
            "Misol:\n512x512"
        )
        context.user_data["mode"] = "both"
        return SIZE
        
    else:
        await update.message.reply_text("Faqat 1, 2 yoki 3 raqamini yozing.")
        return ACTION
```

And the `conv`'s `ACTION` state entry (inside the `states={...}` dict):
```python
    states={
        ACTION: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                action
            )
        ],
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_photo_flow.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_photo_flow.py -v`
Expected: FAIL — `get_photo`'s test fails because the current implementation sends plain text, not `reply_markup`; `action_callback` tests fail with `AttributeError: module 'transparent' has no attribute 'action_callback'`.

- [ ] **Step 3: Implement**

Replace the `get_photo` and `action` functions shown above with:

```python
# ==========================
# RASM QABUL QILISH (Gruppa + Private uchun yangilandi)
# ==========================
ACTION_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("1️⃣ O'lchamni o'zgartirish", callback_data="action:resize")],
    [InlineKeyboardButton("2️⃣ Fonni transparent qilish", callback_data="action:transparent")],
    [InlineKeyboardButton("3️⃣ Ikkalasini ham (Fon + O'lcham)", callback_data="action:both")],
    [InlineKeyboardButton("❌ Bekor qilish", callback_data="flow:cancel")],
])

CANCEL_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Bekor qilish", callback_data="flow:cancel")],
])


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()
    user_id = update.effective_user.id
    path = f"photos/{user_id}.jpg"

    await file.download_to_drive(path)
    context.user_data["photo"] = path
    context.user_data["chat_id"] = update.effective_chat.id  # Guruh yoki private chatni saqlash

    await update.message.reply_text(
        "Rasm qabul qilindi ✅\n\nNima qilamiz?",
        reply_markup=ACTION_KEYBOARD,
    )
    return ACTION
# ==========================
# ACTION TANLASH
# ==========================
async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "flow:cancel":
        await query.edit_message_text("❌ Jarayon bekor qilindi. Yangi rasm yuboring.")
        return ConversationHandler.END

    if choice == "action:resize":
        context.user_data["mode"] = "resize"
        await query.edit_message_text(
            "O'lchamni kiriting (width x height).\n\nMisol:\n512x512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return SIZE

    if choice == "action:both":
        context.user_data["mode"] = "both"
        await query.edit_message_text(
            "O'lchamni kiriting (width x height).\n\nMisol:\n512x512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return SIZE

    # choice == "action:transparent"
    await query.edit_message_text("⏳ Fon olib tashlanmoqda...")
    input_file = context.user_data["photo"]
    output_file = f"photos/{query.from_user.id}_transparent.png"

    result = remove_background(input_file, output_file)

    if result:
        await query.message.reply_document(
            document=open(output_file, "rb"),
            filename="transparent.png",
            caption="✅ Fon transparent qilindi.",
        )
    else:
        await query.message.reply_text("❌ Fon olib tashlashda xatolik yuz berdi.")
    return ConversationHandler.END
```

Then update `conv`'s `ACTION` state entry — replace:

```python
        ACTION: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                action
            )
        ],
```

with:

```python
        ACTION: [
            CallbackQueryHandler(action_callback, pattern=r"^(action:|flow:cancel)")
        ],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_photo_flow.py -v`
Expected: PASS (7 tests)

Then run the full suite: `python3 -m pytest -v` — confirm no regressions in the other 34 pre-existing tests (41 total expected).

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_photo_flow.py
git commit -m "Convert photo action-selection to inline buttons with full-cancel"
```

## Context for Task 1

Tapping "❌ Bekor qilish" at this stage (right after uploading a photo, before any size/mode has been chosen) ends the conversation entirely — there is nothing to "go back" to except re-uploading a photo, so a full cancel is the correct behavior here. The `SIZE`/`LIMIT` states' `flow:cancel` button (added in Task 2) behaves differently — it returns to this action-selection step instead of ending the conversation, because a photo is already stored by then.

`os.makedirs("photos", exist_ok=True)` already runs at module import time (pre-existing code, unrelated to this task) so the real `photos/` directory always exists when the bot actually runs; the tests above create their own isolated `photos/` directories via `tmp_path` where real file I/O is needed (the `action:transparent` tests).

---

## Task 2: "Bekor qilish" at SIZE/LIMIT returns to action selection (not full cancel)

**Files:**
- Modify: `transparent.py` (new `cancel_to_action_selection` function, `conv`'s `SIZE`/`LIMIT` state entries, `resize_size`/`resize_limit` prompt messages)
- Test: `tests/test_cancel_flow.py` (new)

**Current state of `resize_size`/`resize_limit`** (verify by reading the file — these are unchanged since Task 1, which didn't touch them):

```python
# ==========================
# SIZE
# ==========================
async def resize_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not re.match(r"^\d+x\d+$", text):
        await update.message.reply_text(
            "❌ Noto'g'ri format.\n\nMisol:\n512x512"
        )
        return SIZE
    
    width, height = map(int, text.split("x"))
    context.user_data["width"] = width
    context.user_data["height"] = height
    
    await update.message.reply_text(
        "Endi maksimal hajmini KB da yozing.\n\n"
        "Misol:\n512"
    )
    return LIMIT


# ==========================
# LIMIT + Rasmni qayta ishlash
# ==========================
async def resize_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Faqat son yozing.\nMisol: 512")
        return LIMIT
    
    max_kb = int(text)
    input_file = context.user_data["photo"]
    ...
```

And `conv`'s `SIZE`/`LIMIT` state entries (unchanged since before Task 1):

```python
        SIZE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_size
            )
        ],
        LIMIT: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_limit
            )
        ]
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cancel_flow.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cancel_flow.py -v`
Expected: FAIL — `cancel_to_action_selection` tests fail with `AttributeError`; the `resize_size`/`resize_limit` tests fail because `kwargs["reply_markup"]` raises `KeyError` (no `reply_markup` currently passed).

- [ ] **Step 3: Implement**

Add `cancel_to_action_selection` to `transparent.py`, right after `action_callback` (from Task 1):

```python
async def cancel_to_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "photo" not in context.user_data:
        await query.edit_message_text("Iltimos, rasmni qaytadan yuboring.")
        return ConversationHandler.END
    await query.edit_message_text(
        "Rasm qabul qilindi ✅\n\nNima qilamiz?",
        reply_markup=ACTION_KEYBOARD,
    )
    return ACTION
```

Update `resize_size` — replace:

```python
async def resize_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not re.match(r"^\d+x\d+$", text):
        await update.message.reply_text(
            "❌ Noto'g'ri format.\n\nMisol:\n512x512"
        )
        return SIZE
    
    width, height = map(int, text.split("x"))
    context.user_data["width"] = width
    context.user_data["height"] = height
    
    await update.message.reply_text(
        "Endi maksimal hajmini KB da yozing.\n\n"
        "Misol:\n512"
    )
    return LIMIT
```

with:

```python
async def resize_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not re.match(r"^\d+x\d+$", text):
        await update.message.reply_text(
            "❌ Noto'g'ri format.\n\nMisol:\n512x512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return SIZE
    
    width, height = map(int, text.split("x"))
    context.user_data["width"] = width
    context.user_data["height"] = height
    
    await update.message.reply_text(
        "Endi maksimal hajmini KB da yozing.\n\n"
        "Misol:\n512",
        reply_markup=CANCEL_KEYBOARD,
    )
    return LIMIT
```

Update `resize_limit`'s invalid-input branch — replace:

```python
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Faqat son yozing.\nMisol: 512")
        return LIMIT
```

with:

```python
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(
            "Faqat son yozing.\nMisol: 512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return LIMIT
```

Update `conv`'s `SIZE`/`LIMIT` state entries — replace:

```python
        SIZE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_size
            )
        ],
        LIMIT: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_limit
            )
        ]
```

with:

```python
        SIZE: [
            CallbackQueryHandler(cancel_to_action_selection, pattern=r"^flow:cancel$"),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_size
            )
        ],
        LIMIT: [
            CallbackQueryHandler(cancel_to_action_selection, pattern=r"^flow:cancel$"),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_limit
            )
        ]
```

(The `CallbackQueryHandler` is listed before the `MessageHandler` in each state's list so a `flow:cancel` tap is checked first; this doesn't change text-input handling since callback queries and text messages are different update types and never compete for the same update.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cancel_flow.py -v`
Expected: PASS (5 tests)

Then run the full suite: `python3 -m pytest -v` — expect 46 passed (41 from after Task 1 + 5 new, no regressions).

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_cancel_flow.py
git commit -m "Add back-to-action-selection cancel handling at SIZE/LIMIT steps"
```

---

## Task 3: Add "🏠 /start" button to admin and user reply keyboards

**Files:**
- Modify: `transparent.py` (`ADMIN_KEYBOARD`, new `USER_KEYBOARD`, `start`, `main`)
- Modify: `tests/test_start_handler.py` (update one existing test, add one new test)

**Current state** (verify by reading the file):

```python
ADMIN_MENU_USERS = "👥 Foydalanuvchilar soni"
ADMIN_MENU_USERLIST = "📋 Foydalanuvchilar ro'yxati"
ADMIN_MENU_SETTINGS = "⚙️ Sozlamalar"

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [[ADMIN_MENU_USERS], [ADMIN_MENU_USERLIST], [ADMIN_MENU_SETTINGS]],
    resize_keyboard=True,
)
```

`start()`'s keyboard selection:
```python
    keyboard = ADMIN_KEYBOARD if is_admin(user.id) else None
```

`main()`'s button-menu registrations:
```python
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERS]), users_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERLIST]), userlist_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_SETTINGS]), settings_cmd))
```

The existing test that will need updating (`tests/test_start_handler.py`):
```python
async def test_start_sends_no_keyboard_to_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    update = make_update(user_id=1, username="alice", first_name="Alice")
    context = MagicMock()

    await transparent.start(update, context)

    _, kwargs = update.message.reply_text.call_args
    assert kwargs.get("reply_markup") is None
```

- [ ] **Step 1: Write the failing tests**

In `tests/test_start_handler.py`, replace the `test_start_sends_no_keyboard_to_non_admin` test with:

```python
async def test_start_sends_start_button_keyboard_to_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    update = make_update(user_id=1, username="alice", first_name="Alice")
    context = MagicMock()

    await transparent.start(update, context)

    _, kwargs = update.message.reply_text.call_args
    markup = kwargs["reply_markup"]
    labels = [button.text for row in markup.keyboard for button in row]
    assert labels == ["🏠 /start"]
```

Also add this new test to the same file (anywhere after the imports/fixtures):

```python
async def test_admin_keyboard_is_a_2x2_grid_including_start():
    labels = [[button.text for button in row] for row in transparent.ADMIN_KEYBOARD.keyboard]

    assert labels == [
        ["🏠 /start", "👥 Foydalanuvchilar soni"],
        ["📋 Foydalanuvchilar ro'yxati", "⚙️ Sozlamalar"],
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_start_handler.py -v -k "start_button_keyboard or 2x2"`
Expected: FAIL — `test_start_sends_start_button_keyboard_to_non_admin` fails because `reply_markup` is currently `None` for non-admins; `test_admin_keyboard_is_a_2x2_grid_including_start` fails because the current layout is 3 rows of 1 button each, with no `"🏠 /start"`.

- [ ] **Step 3: Implement**

Replace:

```python
ADMIN_MENU_USERS = "👥 Foydalanuvchilar soni"
ADMIN_MENU_USERLIST = "📋 Foydalanuvchilar ro'yxati"
ADMIN_MENU_SETTINGS = "⚙️ Sozlamalar"

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [[ADMIN_MENU_USERS], [ADMIN_MENU_USERLIST], [ADMIN_MENU_SETTINGS]],
    resize_keyboard=True,
)
```

with:

```python
ADMIN_MENU_START = "🏠 /start"
ADMIN_MENU_USERS = "👥 Foydalanuvchilar soni"
ADMIN_MENU_USERLIST = "📋 Foydalanuvchilar ro'yxati"
ADMIN_MENU_SETTINGS = "⚙️ Sozlamalar"

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [ADMIN_MENU_START, ADMIN_MENU_USERS],
        [ADMIN_MENU_USERLIST, ADMIN_MENU_SETTINGS],
    ],
    resize_keyboard=True,
)

USER_KEYBOARD = ReplyKeyboardMarkup(
    [[ADMIN_MENU_START]],
    resize_keyboard=True,
)
```

Replace `start()`'s keyboard selection line:

```python
    keyboard = ADMIN_KEYBOARD if is_admin(user.id) else None
```

with:

```python
    keyboard = ADMIN_KEYBOARD if is_admin(user.id) else USER_KEYBOARD
```

In `main()`, add a new registration alongside the existing three button-menu handlers — replace:

```python
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERS]), users_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERLIST]), userlist_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_SETTINGS]), settings_cmd))
```

with:

```python
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_START]), start))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERS]), users_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERLIST]), userlist_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_SETTINGS]), settings_cmd))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_start_handler.py -v`
Expected: PASS (all tests in the file, including the 2 new/updated ones)

Then run the full suite: `python3 -m pytest -v` — expect 47 passed total (46 from after Task 2, minus 1 replaced test, plus 2 in this task = 47), no regressions.

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_start_handler.py
git commit -m "Add /start button to admin and user reply keyboards"
```

---

## Task 4: Final verification and push

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite one more time**

Run: `python3 -m pytest -v`
Expected: 47 passed, 0 failed

- [ ] **Step 2: Syntax/sanity check**

Run: `python3 -c "import ast; ast.parse(open('transparent.py').read()); print('syntax OK')"`
Expected: `syntax OK`

- [ ] **Step 3: Push to GitHub**

```bash
git push origin main
```

Note: this repo works directly on `main` (no feature branch), per prior project convention established earlier in this codebase's history — do not create a branch for this.

---

## Self-Review Notes

- **Spec coverage:** Section 1 (inline action buttons) → Task 1. Section 2 (state-dependent cancel behavior) → Tasks 1 (full-cancel at ACTION) + 2 (back-to-selection at SIZE/LIMIT). Section 3 (`/start` button, 2x2 admin grid, user keyboard) → Task 3. "Xato holatlari" (missing photo on cancel) → covered in Task 2's `cancel_to_action_selection`. All spec sections have a corresponding task.
- **Type consistency:** `ACTION_KEYBOARD` and `CANCEL_KEYBOARD` are defined once in Task 1 and reused as-is (not redefined) in Task 2's `cancel_to_action_selection` and in `resize_size`/`resize_limit`. `flow:cancel` callback_data string is identical everywhere it's used (Task 1's `ACTION_KEYBOARD`/`CANCEL_KEYBOARD`, Task 1's `action_callback`, Task 2's `conv` SIZE/LIMIT registrations). `ADMIN_MENU_START` is defined once in Task 3 and reused in both `ADMIN_KEYBOARD`, `USER_KEYBOARD`, and the `main()` registration.
- **No placeholders:** every step has complete, real code and exact test assertions; the manual Telegram smoke test is intentionally out of scope for this plan (no live bot session available in the dev environment) — Task 4's verification is limited to automated tests + syntax check + push, consistent with how the original admin-panel plan handled this same constraint.
