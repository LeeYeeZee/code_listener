"""
用户相关 API 路由：注册与登录
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db import crud
from core.security import verify_password, create_access_token

router = APIRouter()

@router.post("/register")
async def register(username: str, password: str, db: AsyncSession = Depends(get_db)):
    existing = await crud.get_user_by_username(db, username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user = await crud.create_user(db, username, password)
    return {"id": user.id, "username": user.username}

@router.post("/login")
async def login(username: str, password: str, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
