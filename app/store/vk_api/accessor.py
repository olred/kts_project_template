import asyncio
import random
import typing
from io import BytesIO

import requests
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


class FilesOpener(object):
    def __init__(self, paths, key_format='file{}'):
        if not isinstance(paths, list):
            paths = [paths]

        self.paths = paths
        self.key_format = key_format
        self.opened_files = []

    def __enter__(self):
        return self.open_files()

    def __exit__(self, type, value, traceback):
        self.close_files()

    def open_files(self):
        self.close_files()

        files = []

        for x, file in enumerate(self.paths):
            if hasattr(file, 'read'):
                f = file

                if hasattr(file, 'name'):
                    filename = file.name
                else:
                    filename = '.jpg'
            else:
                filename = file
                f = open(filename, 'rb')
                self.opened_files.append(f)

            ext = filename.split('.')[-1]
            files.append(
                (self.key_format.format(x), ('file{}.{}'.format(x, ext), f))
            )

        return files

    def close_files(self):
        for f in self.opened_files:
            f.close()

        self.opened_files = []
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
            a = await resp.json()
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
                    "wait": 30,
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


    async def get_messages_server(self, app, chat_id):
        async with self.session.get(
            self._build_query(
                API_PATH,
                "photos.getMessagesUploadServer",
                params={
                    "peer_id": chat_id,
                    "fields": "photo_400_orig",
                    "access_token": self.app.config.bot.token,
                },
            )
                ) as resp:
            data = (await resp.json())["response"]
            return data["upload_url"]


    async def get_photo(self, app, user_ids, chat_id):
        user_ids = ",".join(user_ids)
        async with self.session.get(
            self._build_query(
                API_PATH,
                "users.get",
                params={
                    "user_ids": user_ids,
                    "fields": "photo_400_orig",
                    "access_token": self.app.config.bot.token,
                },
            )
                ) as resp:
            data = (await resp.json())["response"]
            return [i["photo_400_orig"] for i in data]



    async def save_photo(self, app, photo_links, chat_id):
        url = await self.get_messages_server(app, chat_id)
        massiv = []
        tasks = []
        for i in photo_links:
            img = requests.get(i).content
            f = BytesIO(img)
            with FilesOpener(f) as photo_files:
                response = requests.post(url, files=photo_files)
                answer = response.json()
                massiv.append(answer)
        return massiv

    async def process_of_get_fields(self, app, object, result):
        async with self.session.get(
                self._build_query(
                    API_PATH,
                    "photos.saveMessagesPhoto",
                    params={
                        "photo": object["photo"],
                        "server": object["server"],
                        "hash": object["hash"],
                        "access_token": self.app.config.bot.token
                    },
                )
        ) as resp:
            photo_attr = (await resp.json())["response"][-1]
            result.append((photo_attr["id"], photo_attr["access_key"], photo_attr["owner_id"]))

    async def download_photo(self, app, user_ids, chat_id):
        photo_links = await self.get_photo(app, user_ids, chat_id)
        data = await self.save_photo(app, photo_links, chat_id)
        result = []
        tasks = []
        for i in data:
            tasks.append(asyncio.create_task(self.process_of_get_fields(app, i, result)))
        await asyncio.gather(*tasks)
        return result




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
            photo_fields = await self.app.store.vk_api.download_photo(app, [str(i[1]) for i in participants], chat_id)
            participants = list(zip(participants, photo_fields))
            return participants
