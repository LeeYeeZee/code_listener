"""
通知服务：任务状态变更时发送通知（模拟实现）
"""
import asyncio
from typing import Callable

class NotificationService:
    listeners: list[Callable] = []

    def register(self, callback: Callable):
        self.listeners.append(callback)

    async def notify_task_changed(self, task_id: int, new_status: str):
        for listener in self.listeners:
            asyncio.create_task(listener(task_id, new_status))

notifier = NotificationService()
