from datetime import datetime, timedelta, timezone

from capability_commons.api.auth import generate_key, hash_key, is_key_expired
from capability_commons.db.models import ApiKey


def test_generate_key_format():
    raw, hashed = generate_key()
    assert raw.startswith("cc_")
    assert len(raw) > 30
    assert hashed == hash_key(raw)


def test_hash_key_deterministic():
    assert hash_key("test123") == hash_key("test123")
    assert hash_key("test123") != hash_key("test456")


def test_api_key_model_has_expire_at():
    """ApiKey model should have an expire_at column."""
    assert hasattr(ApiKey, "expire_at")


def test_expired_key_check():
    """The auth module should correctly identify expired keys."""
    now = datetime.now(timezone.utc)
    # Not expired (future)
    assert is_key_expired(now + timedelta(hours=1)) is False
    # Expired (past)
    assert is_key_expired(now - timedelta(hours=1)) is True
    # No expiry set
    assert is_key_expired(None) is False
