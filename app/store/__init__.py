import asyncio
import typing

from app.store.database.database import Database

if typing.TYPE_CHECKING:
    from app.web.app import Application


class Store:
    def __init__(self, app: "Application"):
        from app.store.vk_api.accessor import VkApiAccessor
        from app.store.bot.manager import BotManager
        from app.store.bot.sender import VKSender

        self.queue = asyncio.Queue()
        self.out_queue = asyncio.Queue()
        self.vk_api = VkApiAccessor(app)
        self.bot_manager = BotManager(self.queue, self.out_queue, app, 1)
        self.vk_sender = VKSender(self.out_queue, app)


def setup_store(app: "Application"):
    app.database = Database(app)
    app.store = Store(app)
