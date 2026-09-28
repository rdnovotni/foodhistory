import pytest

from app.repository import decode_cursor, encode_cursor


def test_cursor_round_trip():
    cursor = encode_cursor("apple pie", "FH-123")
    assert decode_cursor(cursor, 2) == ["apple pie", "FH-123"]


def test_invalid_cursor_is_rejected():
    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_cursor("not-base64", 2)


def test_cursor_shape_is_checked():
    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_cursor(encode_cursor("one"), 2)
