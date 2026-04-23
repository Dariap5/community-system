from __future__ import annotations

from fastapi import Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def verify_secret(secret: str = Path(...)) -> str:
    if secret != settings.admin_secret_path:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Not Found"},
        )
    return secret
