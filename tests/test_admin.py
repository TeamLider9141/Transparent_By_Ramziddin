import transparent


def test_parse_admin_ids_normal_comma_separated():
    assert transparent._parse_admin_ids("111,222, 333") == {111, 222, 333}


def test_parse_admin_ids_empty_string():
    assert transparent._parse_admin_ids("") == set()


def test_parse_admin_ids_skips_invalid_tokens():
    assert transparent._parse_admin_ids("123, abc, 456") == {123, 456}


def test_is_admin_true_for_known_id(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {111, 222})
    assert transparent.is_admin(111) is True


def test_is_admin_false_for_unknown_id(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", {111, 222})
    assert transparent.is_admin(999) is False


def test_is_admin_false_when_no_admins_configured(monkeypatch):
    monkeypatch.setattr(transparent, "ADMIN_IDS", set())
    assert transparent.is_admin(111) is False
