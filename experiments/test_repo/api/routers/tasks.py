"""
任务相关 API 路由：创建、查询、更新任务状态
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db import crud
from db.models import TaskStatus
from core.config import settings

router = APIRouter()

current_user_id = 1  # 简化：假设所有请求来自用户ID=1

@router.post("/")
async def create_task(title: str, description: str = "", db: AsyncSession = Depends(get_db)):
    count = await crud.count_user_tasks(db, current_user_id)
    if count >= settings.MAX_TASKS_PER_USER:
        raise HTTPException(status_code=403, detail="Task limit reached")
    task = await crud.create_task(db, title, description, current_user_id)
    return {"id": task.id, "title": task.title, "status": task.status.value}

@router.get("/")
async def list_tasks(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    tasks = await crud.get_tasks_by_owner(db, current_user_id, skip, limit)
    return [{"id": t.id, "title": t.title, "status": t.status.value} for t in tasks]

@router.patch("/{task_id}/status")
async def change_status(task_id: int, status: TaskStatus, db: AsyncSession = Depends(get_db)):
    task = await crud.update_task_status(db, task_id, current_user_id, status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"id": task.id, "status": task.status.value}
