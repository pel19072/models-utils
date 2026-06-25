from datetime import timedelta

from database_utils.utils.token_utils import generate_token, is_token_valid
from database_utils.utils.timezone_utils import now_gt


def test_generate_token_returns_unique_strings():
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100


def test_generate_token_returns_nonempty_string():
    token = generate_token()
    assert isinstance(token, str)
    assert len(token) > 0


def test_is_token_valid_when_fresh_and_unused():
    expires_at = now_gt() + timedelta(hours=1)
    assert is_token_valid(expires_at, None) is True


def test_is_token_valid_false_when_expired():
    expires_at = now_gt() - timedelta(seconds=1)
    assert is_token_valid(expires_at, None) is False


def test_is_token_valid_false_when_already_used():
    expires_at = now_gt() + timedelta(hours=1)
    assert is_token_valid(expires_at, now_gt()) is False
