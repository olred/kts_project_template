import asyncio
import typing

from app.store.vk_api.dataclasses import Message, Attachment, MessageKeyboard

if typing.TYPE_CHECKING:
    from app.web.app import Application


class VKSender:
    def __init__(self, out_queue, app: "Application"):
        self.app = app
        self._tasks: typing.List[asyncio.Task] = []
        self.out_queue = out_queue

    async def send_vk(self, upd):
        if upd[0] == "message":
            await self.app.store.vk_api.send_message(
                Message(chat_id=upd[1], text=upd[2]), self.app
            )
        if upd[0] == "photo":
            await self.app.store.vk_api.send_photo(
                Attachment(
                    chat_id=upd[1],
                    attachment=upd[3],
                    text=upd[2],
                ),
                self.app,
            )
        if upd[0] == "keyboard":
            await self.app.store.vk_api.send_message(
                MessageKeyboard(chat_id=upd[1], text=upd[2], keyboard=upd[3]),
                self.app,
            )

    async def _worker(self):
        while True:
            try:
                upd = await self.out_queue.get()
                await self.send_vk(upd)
            finally:
                self.out_queue.task_done()

    async def start(self):
        asyncio.create_task(self._worker())

    async def stop(self):
        await self.out_queue.join()
        for t in self._tasks:
            t.cancel()
