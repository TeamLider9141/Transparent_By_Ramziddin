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
