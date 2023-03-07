import asyncio
from asyncio import Task
from typing import Optional
from app.store import Store


class Poller:
    def __init__(self, in_queue, store: Store):
        self.store = store
        self.is_running = False
        self.poll_task: Optional[Task] = None
        self.in_queue = in_queue

    async def start(self, app):
        self.is_running = True
        self.poll_task = asyncio.create_task(self.poll(app))

    async def stop(self):
        self.is_running = False
        self.poll_task.cancel()

    async def poll(self, app):
        while self.is_running:
            updates = await self.store.vk_api.poll(app)
            for u in updates:
                self.in_queue.put_nowait(u)
