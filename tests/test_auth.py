from capability_commons.api.auth import generate_key, hash_key


def test_generate_key_format():
    raw, hashed = generate_key()
    assert raw.startswith("cc_")
    assert len(raw) > 30
    assert hashed == hash_key(raw)


def test_hash_key_deterministic():
    assert hash_key("test123") == hash_key("test123")
    assert hash_key("test123") != hash_key("test456")
