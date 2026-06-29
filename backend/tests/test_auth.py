import uuid

from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_roundtrip():
    h = hash_password("s3cret-pass")
    assert h != "s3cret-pass"  # never stored in plaintext
    assert verify_password("s3cret-pass", h) is True


def test_verify_rejects_wrong_password():
    h = hash_password("correct-horse")
    assert verify_password("battery-staple", h) is False


def test_verify_handles_garbage_hash():
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_each_hash_is_uniquely_salted():
    assert hash_password("same") != hash_password("same")


def test_token_roundtrip_carries_subject():
    uid = str(uuid.uuid4())
    token = create_access_token(uid)
    assert decode_access_token(token) == uid


def test_decode_rejects_tampered_token():
    token = create_access_token(str(uuid.uuid4()))
    assert decode_access_token(token + "x") is None


def test_decode_rejects_expired_token():
    token = create_access_token(str(uuid.uuid4()), expires_days=-1)
    assert decode_access_token(token) is None
