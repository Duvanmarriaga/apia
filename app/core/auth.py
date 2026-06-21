import hashlib
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import ADMIN_SECRET
from app.core import database as db

_api_key_header = APIKeyHeader(name="X-API-Key", scheme_name="ApiKey", auto_error=False)
_admin_key_header = APIKeyHeader(name="X-Admin-Key", scheme_name="AdminKey", auto_error=False)


def generate_key() -> str:
    return secrets.token_hex(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def require_api_key(key: str = Security(_api_key_header)) -> dict:
    if not key:
        raise HTTPException(status_code=401, detail="Header X-API-Key requerido")

    record = await db.get_api_key_by_hash(hash_key(key))

    if record is None:
        raise HTTPException(status_code=401, detail="API key inválida")
    if not record["is_active"]:
        raise HTTPException(status_code=403, detail="API key desactivada")

    await db.touch_api_key(record["id"])
    return record


def require_admin(key: str = Security(_admin_key_header)) -> None:
    if not key or key != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Admin key inválida o ausente")
