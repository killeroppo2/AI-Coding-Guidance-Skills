from jose import jwt

from app.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        hashed = hash_password("test_password")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_differs_from_plaintext(self):
        hashed = hash_password("test_password")
        assert hashed != "test_password"

    def test_verify_password_correct(self):
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_same_password_different_hashes(self):
        """Same password produces different hashes due to salt."""
        hash1 = hash_password("password")
        hash2 = hash_password("password")
        assert hash1 != hash2

    def test_verify_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True


class TestJWT:
    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "test_user"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        token = create_access_token({"sub": "test_user"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "test_user"
        assert payload["type"] == "access"

    def test_decode_token_with_custom_claims(self):
        token = create_access_token({"sub": "user123", "role": "admin"})
        payload = decode_token(token)
        assert payload["sub"] == "user123"
        assert payload["role"] == "admin"

    def test_decode_expired_token(self):
        """Token with negative expiry should be rejected."""
        original = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        try:
            settings.ACCESS_TOKEN_EXPIRE_MINUTES = -1
            token = create_access_token({"sub": "test_user"})
        finally:
            settings.ACCESS_TOKEN_EXPIRE_MINUTES = original
        payload = decode_token(token)
        assert payload is None

    def test_decode_invalid_token(self):
        payload = decode_token("invalid_token_string")
        assert payload is None

    def test_decode_tampered_token(self):
        token = create_access_token({"sub": "test_user"})
        tampered = token[:-5] + "XXXXX"
        payload = decode_token(tampered)
        assert payload is None

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "test_user"})
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in decoded
        assert isinstance(decoded["exp"], int)
