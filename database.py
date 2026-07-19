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
        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return cursor.rowcount > 0
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
