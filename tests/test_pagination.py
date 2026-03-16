import uuid

from capability_commons.schemas.pagination import PaginatedResponse, PaginationParams


def test_cursor_encode_decode():
    item_id = uuid.uuid4()
    cursor = PaginatedResponse.encode_cursor(item_id)
    params = PaginationParams(cursor=cursor, limit=10)
    decoded = params.decode_cursor()
    assert decoded == item_id


def test_cursor_none():
    params = PaginationParams(limit=10)
    assert params.decode_cursor() is None


def test_limit_bounds():
    p = PaginationParams(limit=1)
    assert p.limit == 1
    p = PaginationParams(limit=100)
    assert p.limit == 100
