# tests/unit/test_auth_password.py
from src.auth.password import hash_password, verify_password


def test_hash_is_not_plaintext():
    assert hash_password("secret") != "secret"


def test_correct_password_verifies():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed) is True


def test_wrong_password_fails():
    hashed = hash_password("secret")
    assert verify_password("wrongpassword", hashed) is False
