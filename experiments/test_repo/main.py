"""
TaskFlow - 任务管理后端服务入口
"""
from fastapi import FastAPI
from api.routers import tasks, users
from db.database import init_db
from core.config import settings

app = FastAPI(title="TaskFlow API", version="1.0.0")

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(users.router, prefix="/users", tags=["users"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.ENV}
