import os
from unittest.mock import MagicMock

import pytest

import transparent


# ---------- _mask_api_key ----------

def test_mask_api_key_long():
    assert transparent._mask_api_key("uwfYNenrqyEbw6VBCw6wF5Ep") == "uwfY...F5Ep"


def test_mask_api_key_short_is_fully_masked():
    assert transparent._mask_api_key("abc") == "****"


def test_mask_api_key_exactly_eight_is_masked():
    # 8 chars: not long enough to reveal first4+last4 without overlap, fully masked
    assert transparent._mask_api_key("abcdefgh") == "****"


# ---------- _validate_remove_bg_key ----------

def test_validate_key_valid(monkeypatch):
    resp = MagicMock()
    resp.status_code = 200
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return resp

    monkeypatch.setattr(transparent.requests, "get", fake_get)

    assert transparent._validate_remove_bg_key("goodkey") == "valid"
    assert captured["url"] == "https://api.remove.bg/v1.0/account"
    assert captured["headers"] == {"X-Api-Key": "goodkey"}


def test_validate_key_invalid_403(monkeypatch):
    resp = MagicMock()
    resp.status_code = 403
    monkeypatch.setattr(transparent.requests, "get", lambda *a, **k: resp)
    assert transparent._validate_remove_bg_key("badkey") == "invalid"


def test_validate_key_invalid_401(monkeypatch):
    resp = MagicMock()
    resp.status_code = 401
    monkeypatch.setattr(transparent.requests, "get", lambda *a, **k: resp)
    assert transparent._validate_remove_bg_key("badkey") == "invalid"


def test_validate_key_other_status_is_error(monkeypatch):
    resp = MagicMock()
    resp.status_code = 500
    monkeypatch.setattr(transparent.requests, "get", lambda *a, **k: resp)
    assert transparent._validate_remove_bg_key("k") == "error"


def test_validate_key_network_exception_is_error(monkeypatch):
    def boom(*a, **k):
        raise transparent.requests.RequestException("no network")
    monkeypatch.setattr(transparent.requests, "get", boom)
    assert transparent._validate_remove_bg_key("k") == "error"


# ---------- _write_env_value ----------

def test_write_env_replaces_existing_line(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_TOKEN=abc\nREMOVE_BG_API=oldkey\nADMIN_IDS=1,2\n")

    transparent._write_env_value("REMOVE_BG_API", "newkey", path=str(env))

    lines = env.read_text().splitlines()
    assert "TELEGRAM_TOKEN=abc" in lines
    assert "REMOVE_BG_API=newkey" in lines
    assert "REMOVE_BG_API=oldkey" not in lines
    assert "ADMIN_IDS=1,2" in lines
    # order preserved: REMOVE_BG_API stays the 2nd line
    assert lines[1] == "REMOVE_BG_API=newkey"


def test_write_env_appends_when_missing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_TOKEN=abc\n")

    transparent._write_env_value("REMOVE_BG_API", "newkey", path=str(env))

    lines = env.read_text().splitlines()
    assert "TELEGRAM_TOKEN=abc" in lines
    assert "REMOVE_BG_API=newkey" in lines


def test_write_env_creates_file_when_missing(tmp_path):
    env = tmp_path / ".env"  # does not exist yet
    transparent._write_env_value("REMOVE_BG_API", "newkey", path=str(env))
    assert env.read_text().splitlines() == ["REMOVE_BG_API=newkey"]


def test_write_env_handles_no_trailing_newline(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_TOKEN=abc")  # no trailing newline

    transparent._write_env_value("REMOVE_BG_API", "newkey", path=str(env))

    lines = env.read_text().splitlines()
    assert lines == ["TELEGRAM_TOKEN=abc", "REMOVE_BG_API=newkey"]


def test_write_env_ignores_commented_and_whitespace_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("#REMOVE_BG_API=commented\n  REMOVE_BG_API =spacedkey\nOTHER=x\n")

    transparent._write_env_value("REMOVE_BG_API", "newkey", path=str(env))

    text = env.read_text()
    # the commented line is preserved untouched
    assert "#REMOVE_BG_API=commented" in text
    # the whitespace-padded real key line is the one replaced
    assert "REMOVE_BG_API=newkey" in text
    assert "spacedkey" not in text
    assert "OTHER=x" in text
