import hashlib
from datetime import datetime, timezone


def test_ip_hash_consistency():
    ip = "192.168.1.1"
    h1 = f"ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
    h2 = f"ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
    assert h1 == h2


def test_window_truncation():
    now = datetime(2026, 3, 13, 12, 34, 56, 789, tzinfo=timezone.utc)
    window = now.replace(second=0, microsecond=0)
    assert window.second == 0
    assert window.microsecond == 0
    assert window.minute == 34
