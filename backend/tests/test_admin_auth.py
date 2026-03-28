"""Unit tests for admin auth helper functions."""

import hashlib
from unittest.mock import MagicMock

from app.services.admin_auth import _extract_bearer_token, _hash_key


class TestHashKey:
    """Tests for _hash_key()."""

    def test_known_digest(self):
        raw = "my-secret-key"
        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert _hash_key(raw) == expected

    def test_different_inputs_different_hashes(self):
        assert _hash_key("key-a") != _hash_key("key-b")

    def test_deterministic(self):
        assert _hash_key("same") == _hash_key("same")

    def test_empty_string(self):
        expected = hashlib.sha256(b"").hexdigest()
        assert _hash_key("") == expected


class TestExtractBearerToken:
    """Tests for _extract_bearer_token()."""

    def _make_request(self, headers: dict[str, str]) -> MagicMock:
        request = MagicMock()
        request.headers = headers
        return request

    def test_valid_bearer_token(self):
        request = self._make_request({"Authorization": "Bearer my-token-123"})
        assert _extract_bearer_token(request) == "my-token-123"

    def test_bearer_case_insensitive(self):
        request = self._make_request({"Authorization": "bearer my-token"})
        assert _extract_bearer_token(request) == "my-token"

    def test_missing_authorization_header(self):
        request = self._make_request({})
        assert _extract_bearer_token(request) is None

    def test_non_bearer_scheme(self):
        request = self._make_request({"Authorization": "Basic dXNlcjpwYXNz"})
        assert _extract_bearer_token(request) is None

    def test_empty_bearer_value(self):
        request = self._make_request({"Authorization": "Bearer "})
        assert _extract_bearer_token(request) is None

    def test_bearer_token_whitespace_stripped(self):
        request = self._make_request({"Authorization": "Bearer   spaced-token  "})
        assert _extract_bearer_token(request) == "spaced-token"
