import asyncio

from app.store.bot.sender import VKSender
from app.store.vk_api.poller import Poller
from app.store.bot.manager import BotManager
from app.store import Store
from app.web.app import app


class Bot:
    def __init__(self, n):
        self.queue = asyncio.Queue()
        self.out_queue = asyncio.Queue()
        self.store = Store(app)
        self.poller = Poller(self.queue, self.store)
        self.worker = BotManager(self.queue, self.out_queue, app, n)
        self.sender = VKSender(self.out_queue, app)

    async def start(self):
        await self.poller.start(app)
        await self.worker.start()
        await self.sender.start()

    async def stop(self):
        await self.poller.stop()
        await self.worker.stop()
        await self.sender.stop()
