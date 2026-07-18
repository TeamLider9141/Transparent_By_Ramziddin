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
