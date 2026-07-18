# Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track every user who sends `/start`, and give admin(s) `/users`, `/userlist`, and `/settings` commands to see counts and browse the user list; non-admins get an access-denied reply from those three commands.

**Architecture:** A new `database.py` module wraps a SQLite file (`users.db`) with plain functions (`init_db`, `add_user`, `get_user_count`, `get_today_count`, `get_users_page`). `transparent.py` gains an `ADMIN_IDS` set parsed from env, an `is_admin()` guard, and new command/callback handlers that call into `database.py`. Pagination for `/userlist` uses Telegram inline keyboard callback buttons (`userlist:<offset>`), reused by the `/settings` panel's "user list" button.

**Tech Stack:** Python 3.10, python-telegram-bot 22.x, sqlite3 (stdlib), pytest + pytest-asyncio for tests.

---

## Task 1: `database.py` — SQLite user store

**Files:**
- Create: `database.py`
- Test: `tests/test_database.py`
- Create: `tests/__init__.py` (empty, makes `tests` a package)

- [ ] **Step 1: Write the failing tests**

Create `tests/__init__.py` (empty file).

Create `tests/test_database.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_database.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'database'`

- [ ] **Step 3: Write the implementation**

Create `database.py`:

```python
import sqlite3
from datetime import datetime, timezone

DB_PATH = "users.db"


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def add_user(user_id, username, first_name):
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_count():
    conn = _connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def get_today_count():
    today = datetime.now(timezone.utc).date().isoformat()
    conn = _connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]
    finally:
        conn.close()


def get_users_page(offset, limit):
    conn = _connect()
    try:
        return conn.execute(
            "SELECT user_id, username, first_name, joined_at FROM users "
            "ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_database.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add database.py tests/__init__.py tests/test_database.py
git commit -m "Add SQLite user store (database.py)"
```

---

## Task 2: pytest-asyncio config + dev requirements

**Files:**
- Create: `pytest.ini`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

This lets `async def test_...` functions run without decorating each one with `@pytest.mark.asyncio`.

- [ ] **Step 2: Create `requirements-dev.txt`**

```
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 3: Verify pytest picks up the config**

Run: `python3 -m pytest tests/test_database.py -v`
Expected: PASS, no change in behavior (confirms `pytest.ini` doesn't break existing sync tests)

- [ ] **Step 4: Commit**

```bash
git add pytest.ini requirements-dev.txt
git commit -m "Add pytest-asyncio config and dev requirements"
```

---

## Task 3: `ADMIN_IDS` / `is_admin()` in `transparent.py`

**Files:**
- Modify: `transparent.py:1-25` (imports + token section)
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_admin.py`:

```python
import transparent


def test_is_admin_true_for_known_id(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {111, 222})
    assert transparent.is_admin(111) is True


def test_is_admin_false_for_unknown_id(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {111, 222})
    assert transparent.is_admin(999) is False


def test_is_admin_false_when_no_admins_configured(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", set())
    assert transparent.is_admin(111) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_admin.py -v`
Expected: FAIL with `AttributeError: module 'transparent' has no attribute 'ADMIN_IDS'` (or `is_admin`)

- [ ] **Step 3: Implement**

In `transparent.py`, replace lines 20-25:

```python
# ==========================
# TOKENLAR
# ==========================
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REMOVE_BG_API = os.getenv("REMOVE_BG_API")
```

with:

```python
# ==========================
# TOKENLAR
# ==========================
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REMOVE_BG_API = os.getenv("REMOVE_BG_API")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_admin.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_admin.py
git commit -m "Add ADMIN_IDS parsing and is_admin() guard"
```

---

## Task 4: Wire `add_user` into `/start`

**Files:**
- Modify: `transparent.py:1-18` (imports), `transparent.py:37-50` (`start` handler)
- Test: `tests/test_start_handler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_start_handler.py`:

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_start_handler.py -v`
Expected: FAIL on `test_start_records_user_in_db` — `get_user_count()` returns 0, not 1

- [ ] **Step 3: Implement**

In `transparent.py`, add to imports (after line 9, `from dotenv import load_dotenv`):

```python
from database import init_db, add_user, get_user_count, get_today_count, get_users_page
```

Replace the `start` handler (lines 40-50):

```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        "👋 Salom!\n\n"
        "Bu bot Ramziddin Parpiyev tomonidan ishlab chiqarilgan.\n\n"
        "Menga rasm yuboring.\n\n"
        "Men quyidagilarni qila olaman:\n\n"
        "🖼 O'lchamni o'zgartirish\n"
        "📦 Hajmini kamaytirish\n"
        "✂️ Orqa fonni transparent qilish\n\n"
        "Rasm yuboring."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_start_handler.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_start_handler.py
git commit -m "Record user in database on /start"
```

---

## Task 5: `/users` command (admin-only count)

**Files:**
- Modify: `transparent.py` (new handler, placed after `start`)
- Test: `tests/test_users_cmd.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_users_cmd.py`:

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


def make_update(user_id):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    return update


async def test_users_cmd_denies_non_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {999})
    update = make_update(user_id=1)

    await transparent.users_cmd(update, MagicMock())

    update.message.reply_text.assert_awaited_once_with("⛔ Bu buyruq faqat admin uchun.")


async def test_users_cmd_shows_count_for_admin(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {1})
    database.add_user(10, "a", "A")
    database.add_user(11, "b", "B")
    update = make_update(user_id=1)

    await transparent.users_cmd(update, MagicMock())

    update.message.reply_text.assert_awaited_once_with("👥 Jami foydalanuvchilar: 2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_users_cmd.py -v`
Expected: FAIL with `AttributeError: module 'transparent' has no attribute 'users_cmd'`

- [ ] **Step 3: Implement**

In `transparent.py`, add after the `start` handler (after the block added in Task 4):

```python
# ==========================
# ADMIN: FOYDALANUVCHILAR SONI
# ==========================
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        return
    count = get_user_count()
    await update.message.reply_text(f"👥 Jami foydalanuvchilar: {count}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_users_cmd.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_users_cmd.py
git commit -m "Add admin-only /users count command"
```

---

## Task 6: `/userlist` command with pagination

**Files:**
- Modify: `transparent.py` (imports, new handlers)
- Test: `tests/test_userlist.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_userlist.py`:

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_userlist.py -v`
Expected: FAIL with `AttributeError: module 'transparent' has no attribute 'userlist_cmd'`

- [ ] **Step 3: Implement**

In `transparent.py`, add to imports — replace:

```python
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
```

with:

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
```

Add a `PAGE_SIZE` constant near `ADMIN_IDS` (in the TOKENLAR section added in Task 3):

```python
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
PAGE_SIZE = 20


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
```

Add after the `users_cmd` handler (from Task 5):

```python
# ==========================
# ADMIN: FOYDALANUVCHILAR RO'YXATI
# ==========================
def _format_user_line(row):
    user_id, username, first_name, joined_at = row
    uname = f"@{username}" if username else "—"
    name = first_name or "—"
    date = joined_at[:10] if joined_at else "—"
    return f"ID: {user_id} | {uname} | {name} | {date}"


def _build_userlist_page(offset):
    rows = get_users_page(offset, PAGE_SIZE)
    total = get_user_count()
    text = (
        "\n".join(_format_user_line(row) for row in rows)
        if rows
        else "Foydalanuvchilar topilmadi."
    )

    buttons = []
    if offset > 0:
        prev_offset = max(0, offset - PAGE_SIZE)
        buttons.append(InlineKeyboardButton("⬅️ Oldinga", callback_data=f"userlist:{prev_offset}"))
    if offset + PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"userlist:{offset + PAGE_SIZE}"))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None
    return text, markup


async def userlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        return
    text, markup = _build_userlist_page(0)
    await update.message.reply_text(text, reply_markup=markup)


async def userlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    offset = int(query.data.split(":", 1)[1])
    text, markup = _build_userlist_page(offset)
    await query.edit_message_text(text, reply_markup=markup)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_userlist.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_userlist.py
git commit -m "Add admin-only /userlist command with pagination"
```

---

## Task 7: `/settings` admin panel

**Files:**
- Modify: `transparent.py` (new handlers)
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings.py`:

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_settings.py -v`
Expected: FAIL with `AttributeError: module 'transparent' has no attribute 'settings_cmd'`

- [ ] **Step 3: Implement**

In `transparent.py`, add after the `/userlist` block (from Task 6):

```python
# ==========================
# ADMIN: SETTINGS PANEL
# ==========================
async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="settings:stats")],
        [InlineKeyboardButton("👥 Foydalanuvchilar ro'yxati", callback_data="settings:userlist")],
    ])
    await update.message.reply_text("⚙️ Admin panel", reply_markup=keyboard)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    if query.data == "settings:stats":
        total = get_user_count()
        today = get_today_count()
        await query.edit_message_text(f"📊 Statistika\n\nJami: {total}\nBugun: {today}")
    elif query.data == "settings:userlist":
        text, markup = _build_userlist_page(0)
        await query.edit_message_text(text, reply_markup=markup)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_settings.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add transparent.py tests/test_settings.py
git commit -m "Add admin-only /settings panel"
```

---

## Task 8: Register handlers, init DB at startup, update config files

**Files:**
- Modify: `transparent.py:261-269` (renumbered after prior tasks — locate the `def main():` block)
- Modify: `.env`, `.env.example`
- Modify: `.gitignore`
- Modify: `DEPLOY.md`

- [ ] **Step 1: Update `main()` in `transparent.py`**

Replace:

```python
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("🤖 Bot muvaffaqiyatli ishga tushdi... Guruhlar va shaxsiy chatlar uchun tayyor!")
    app.run_polling()
```

with:

```python
def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("userlist", userlist_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CallbackQueryHandler(userlist_callback, pattern=r"^userlist:"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^settings:"))
    app.add_handler(conv)

    print("🤖 Bot muvaffaqiyatli ishga tushdi... Guruhlar va shaxsiy chatlar uchun tayyor!")
    app.run_polling()
```

- [ ] **Step 2: Add `ADMIN_IDS` to `.env` and `.env.example`**

Append to `.env`:
```
ADMIN_IDS=YOUR_TELEGRAM_USER_ID
```

Append to `.env.example`:
```
ADMIN_IDS=123456789,987654321
```

- [ ] **Step 3: Add `users.db` to `.gitignore`**

Append to `.gitignore`:
```
users.db
```

- [ ] **Step 4: Document `ADMIN_IDS` in `DEPLOY.md`**

In `DEPLOY.md`, in the ".env fayl yaratish" section, after the existing `TELEGRAM_TOKEN` / `REMOVE_BG_API` block, add a line:

```
ADMIN_IDS=123456789,987654321
```

and a short note: "`ADMIN_IDS` — admin bo'ladigan Telegram user_id'lar, vergul bilan ajratiladi. O'z Telegram ID'ingizni bilish uchun @userinfobot ga yozing."

- [ ] **Step 5: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: PASS (all tests from Tasks 1, 3, 5, 6, 7 — 18 tests total)

- [ ] **Step 6: Manual smoke test**

This step is not automatable — do it against a real bot token in a private Telegram chat before deploying:
1. Set `ADMIN_IDS` in `.env` to your own Telegram user ID.
2. Run `python3 transparent.py` locally.
3. Send `/start` from your account → confirm normal welcome message.
4. Send `/users` → confirm it shows count `1`.
5. Send `/userlist` → confirm your entry shows up.
6. Send `/settings` → tap "📊 Statistika" and "👥 Foydalanuvchilar ro'yxati" → confirm both update the message.
7. From a second Telegram account (or ask a friend) send `/users`, `/userlist`, `/settings` → confirm each replies "⛔ Bu buyruq faqat admin uchun."

- [ ] **Step 7: Commit**

```bash
git add transparent.py .env.example .gitignore DEPLOY.md
git commit -m "Register admin handlers, init DB at startup, document ADMIN_IDS"
```

Note: `.env` is git-ignored and won't be staged by this command — that's expected, it holds real secrets.

---

## Self-Review Notes

- **Spec coverage:** DB schema (Task 1), admin auth (Task 3), `/start` tracking (Task 4), `/users` (Task 5), `/userlist` + pagination (Task 6), `/settings` (Task 7), file/config changes incl. `.gitignore` for `users.db` (Task 8) — all spec sections covered.
- **Type consistency:** `get_users_page` returns `(user_id, username, first_name, joined_at)` tuples in both `database.py` (Task 1) and `_format_user_line` (Task 6) — matches. `ADMIN_IDS` is a `set[int]` everywhere it's read or monkeypatched.
- **No placeholders:** every step has real code; manual smoke test (Task 8 Step 6) is explicitly called out as non-automatable rather than hand-waved.
