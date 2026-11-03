from db.store import _json_ids


def test_corrupt_json_returns_empty() -> None:
    assert _json_ids("{not json") == ()
    assert _json_ids(b"\xff") == ()


def test_valid_and_non_list() -> None:
    assert _json_ids('["a", 2]') == ("a", "2")
    assert _json_ids("{}") == ()
    assert _json_ids(None) == ()
