"""
数据库 CRUD 操作：封装对 User 和 Task 的增删改查
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.models import User, Task, TaskStatus
from core.security import get_password_hash

async def create_user(db: AsyncSession, username: str, password: str) -> User:
    user = User(username=username, hashed_password=get_password_hash(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def create_task(db: AsyncSession, title: str, description: str, owner_id: int) -> Task:
    task = Task(title=title, description=description, owner_id=owner_id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

async def get_tasks_by_owner(db: AsyncSession, owner_id: int, skip: int = 0, limit: int = 20):
    result = await db.execute(
        select(Task).where(Task.owner_id == owner_id).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def update_task_status(db: AsyncSession, task_id: int, owner_id: int, status: TaskStatus) -> Task | None:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.owner_id == owner_id)
    )
    task = result.scalar_one_or_none()
    if task:
        task.status = status
        await db.commit()
        await db.refresh(task)
    return task

async def count_user_tasks(db: AsyncSession, owner_id: int) -> int:
    result = await db.execute(select(func.count(Task.id)).where(Task.owner_id == owner_id))
    return result.scalar()
