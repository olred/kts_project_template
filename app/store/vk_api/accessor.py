import random
import typing
from typing import Optional
from aiohttp import TCPConnector
from aiohttp.client import ClientSession
from app.base.base_accessor import BaseAccessor
from app.store.vk_api.dataclasses import (
    Message,
    Update,
    UpdateObject,
    UpdatePhoto,
    Attachment,
    UpdateAction,
    MessageKeyboard,
)
from app.store.vk_api.poller import Poller

if typing.TYPE_CHECKING:
    from app.web.app import Application

API_PATH = "https://api.vk.com/method/"


class VkApiAccessor(BaseAccessor):
    def __init__(self, app: "Application", *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.session: Optional[ClientSession] = None
        self.key: Optional[str] = None
        self.server: Optional[str] = None
        self.poller: Optional[Poller] = None
        self.ts: Optional[int] = None

    async def connect(self, app: "Application"):
        self.session = ClientSession(connector=TCPConnector(verify_ssl=False))
        try:
            await self._get_long_poll_service()
        except Exception as e:
            self.logger.error("Exception", exc_info=e)
        self.logger.info("start polling")

    async def disconnect(self, app: "Application"):
        if self.session:
            await self.session.close()
        if self.poller:
            await self.poller.stop()

    @staticmethod
    def _build_query(host: str, method: str, params: dict) -> str:
        url = host + method + "?"
        if "v" not in params:
            params["v"] = "5.132"
        url += "&".join([f"{k}={v}" for k, v in params.items()])
        print(url)
        return url

    async def _get_long_poll_service(self):
        async with self.session.get(
            self._build_query(
                host=API_PATH,
                method="groups.getLongPollServer",
                params={
                    "group_id": self.app.config.bot.group_id,
                    "access_token": self.app.config.bot.token,
                },
            )
        ) as resp:
            data = (await resp.json())["response"]

            self.logger.info(data)
            self.key = data["key"]
            self.server = data["server"]
            self.ts = data["ts"]
            self.logger.info(self.server)

    async def poll(self, app):
        await self.connect(app)
        async with self.session.get(
            self._build_query(
                host=self.server,
                method="",
                params={
                    "act": "a_check",
                    "key": self.key,
                    "ts": self.ts,
                    "wait": 10,
                },
            )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)
            self.ts = data["ts"]
            raw_updates = data.get("updates", [])
            updates = []
            for update in raw_updates:
                updt = update["object"]["message"]["attachments"]
                if len(updt) != 0:
                    for i in updt:
                        if i["type"] == "photo":
                            updates.append(
                                Update(
                                    type=update["type"],
                                    object=UpdatePhoto(
                                        chat_id=update["object"]["message"][
                                            "peer_id"
                                        ],
                                        id=update["object"]["message"]["id"],
                                        body=update["object"]["message"][
                                            "text"
                                        ],
                                        type=i["type"],
                                        owner_id=i["photo"]["owner_id"],
                                        photo_id=i["photo"]["id"],
                                        access_key=i["photo"]["access_key"],
                                    ),
                                )
                            )
                else:
                    try:
                        updates.append(
                            Update(
                                type=update["type"],
                                object=UpdateAction(
                                    chat_id=update["object"]["message"][
                                        "peer_id"
                                    ],
                                    id=update["object"]["message"]["from_id"],
                                    body=update["object"]["message"]["text"],
                                    type=update["object"]["message"]["action"][
                                        "type"
                                    ],
                                    member_id=update["object"]["message"][
                                        "action"
                                    ]["member_id"],
                                ),
                            )
                        )
                    except KeyError:
                        updates.append(
                            Update(
                                type=update["type"],
                                object=UpdateObject(
                                    chat_id=update["object"]["message"][
                                        "peer_id"
                                    ],
                                    id=update["object"]["message"]["from_id"],
                                    body=update["object"]["message"]["text"],
                                    type="other_type",
                                ),
                            )
                        )
        await self.disconnect(app)
        return updates

    async def send_message(
        self, message: Message | MessageKeyboard, app
    ) -> None:
        await self.connect(app)
        if type(message) is Message:
            parametrs = {
                "random_id": random.randint(1, 2**32),
                "peer_id": message.chat_id,
                "message": message.text,
                "access_token": self.app.config.bot.token,
            }
        else:
            print(1)
            parametrs = {
                "random_id": random.randint(1, 2**32),
                "peer_id": message.chat_id,
                "message": message.text,
                "keyboard": message.keyboard,
                "access_token": self.app.config.bot.token,
            }
        async with self.session.get(
            self._build_query(API_PATH, "messages.send", params=parametrs)
        ) as resp:
            data = await resp.json()
            self.logger.info(data)
        await self.disconnect(app)

    @staticmethod
    def _build_attachment(attach_mass: list[str]):
        spisok = []
        for i in attach_mass:
            stroka = f"photo{i[0]}_{i[1]}_{i[2]}"
            spisok.append(stroka)
        return ",".join(spisok)

    async def send_photo(self, attachment: Attachment, app) -> None:
        await self.connect(app)
        attachments = self._build_attachment(attachment.attachment)
        async with self.session.get(
            self._build_query(
                API_PATH,
                "messages.send",
                params={
                    "random_id": random.randint(1, 2**32),
                    "peer_id": attachment.chat_id,
                    "attachment": attachments,
                    "message": attachment.text,
                    "access_token": self.app.config.bot.token,
                },
            )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)
        await self.disconnect(app)

    async def make_userlist(self, chat_id, app):
        await self.connect(app)
        async with self.session.get(
            self._build_query(
                API_PATH,
                "messages.getConversationMembers",
                params={
                    "peer_id": chat_id,
                    "access_token": self.app.config.bot.token,
                },
            )
        ) as resp:
            data = await resp.json()
            participants = []
            for i in range(data["response"]["count"] - 1):
                full_name = f'@{data["response"]["profiles"][i]["screen_name"]}'
                id_profile = data["response"]["profiles"][i]["id"]
                participants.append((full_name, id_profile))
                await self.disconnect(app)
            return participants
