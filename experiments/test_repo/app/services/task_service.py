"""
任务业务逻辑层：协调数据库与路由之间的复杂操作
"""
from sqlalchemy.ext.asyncio import AsyncSession
from db import crud
from db.models import TaskStatus

class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_with_validation(self, title: str, description: str, owner_id: int, max_tasks: int):
        count = await crud.count_user_tasks(self.db, owner_id)
        if count >= max_tasks:
            raise ValueError("Exceeds maximum task limit")
        return await crud.create_task(self.db, title, description, owner_id)

    async def batch_update_status(self, task_ids: list[int], owner_id: int, status: TaskStatus):
        updated = []
        for tid in task_ids:
            task = await crud.update_task_status(self.db, tid, owner_id, status)
            if task:
                updated.append(task.id)
        return updated
