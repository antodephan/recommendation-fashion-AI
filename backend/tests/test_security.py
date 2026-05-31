"""Unit tests for security utilities."""

from app.core.security import (
    create_token,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_round_trip():
    h = hash_password("secret-pass-123")
    assert verify_password("secret-pass-123", h)
    assert not verify_password("wrong", h)


def test_token_round_trip():
    token = create_token("user-1", "access")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"


def test_token_pair():
    a, r = create_token_pair("uid")
    pa = decode_token(a, expected_type="access")
    pr = decode_token(r, expected_type="refresh")
    assert pa["sub"] == pr["sub"] == "uid"
    assert pa["jti"] != pr["jti"]
