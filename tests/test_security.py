import pytest

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.enums import UserRole


class TestHashPassword:
    def test_returns_hex_string(self):
        result = hash_password("secret")
        assert isinstance(result, str)
        assert len(result) == 64  # sha256 hex digest

    def test_is_deterministic(self):
        assert hash_password("abc") == hash_password("abc")

    def test_different_inputs_produce_different_hashes(self):
        assert hash_password("password1") != hash_password("password2")


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


class TestCreateAndDecodeToken:
    def test_decode_returns_expected_fields(self):
        token = create_access_token(user_id=42, email="u@example.com", role=UserRole.ADMIN)
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["email"] == "u@example.com"
        assert payload["role"] == "admin"

    def test_token_with_string_role(self):
        token = create_access_token(user_id=1, email=None, role="employee")
        payload = decode_access_token(token)
        assert payload["role"] == "employee"

    def test_decode_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token("not.a.valid.token")

    def test_decode_tampered_token_raises(self):
        token = create_access_token(user_id=1, email="a@b.com", role=UserRole.EMPLOYEE)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError):
            decode_access_token(tampered)
