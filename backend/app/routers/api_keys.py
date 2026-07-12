"""Bring-your-own-key management: each user pastes their own DashScope key so
their dramas bill their own Qwen Cloud account, not the operator's."""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.api_keys import encrypt_key, decrypt_key, set_request_key

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


class KeyIn(BaseModel):
    api_key: str


def _status(user: User) -> dict:
    s = get_settings()
    raw = decrypt_key(user.dashscope_key_enc)
    return {
        "configured": bool(raw),
        "tail": raw[-4:] if raw else None,
        # whether this deploy insists on a personal key for paid work
        "required": s.require_user_api_key,
        # whether the server has a fallback key at all (never exposed)
        "server_fallback": bool(s.qwen_api_key) and not s.require_user_api_key,
    }


@router.get("")
def get_key_status(user: User = Depends(get_current_user)):
    return _status(user)


@router.put("")
async def set_key(body: KeyIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    key = (body.api_key or "").strip()
    if not key or len(key) < 10:
        raise HTTPException(status_code=400, detail="That does not look like a DashScope API key.")
    # live validation: one minimal qwen-flash call against the intl endpoint —
    # a wrong or China-console key fails here instead of mid-generation
    s = get_settings()
    async with httpx.AsyncClient() as http:
        r = await http.post(
            s.qwen_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "qwen-flash", "max_tokens": 1,
                  "messages": [{"role": "user", "content": "hi"}]},
            timeout=30.0)
    if r.status_code in (401, 403):
        raise HTTPException(status_code=400, detail=(
            "Qwen Cloud rejected this key. Check it is an API key from the "
            "INTERNATIONAL Model Studio console (dashscope-intl), not the China console."))
    if r.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Key check failed ({r.status_code}): {r.text[:200]}")
    user.dashscope_key_enc = encrypt_key(key)
    db.commit()
    set_request_key(key)
    return _status(user)


@router.delete("")
def delete_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.dashscope_key_enc = None
    db.commit()
    set_request_key(None)
    return _status(user)
