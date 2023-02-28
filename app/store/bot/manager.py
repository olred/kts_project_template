import typing
from logging import getLogger
from time import sleep, time
from random import choice
from sqlalchemy.sql import select, update as refresh

from app.store.bot.services import make_grid, check_winner
from app.store.vk_api.dataclasses import Message, Update, Attachment, UpdateObject
from app.web.app import app
from app.store.models.model import ParticipantsModel

if typing.TYPE_CHECKING:
    from app.web.app import Application


class SM:
    def __init__(self):
        self.state_photo = False
        self.state_in_game = False
        self.state_wait_votes = False
        self.users = None
        self.new_pair = None
        self.voters_dict = {}
        self.voters = []
        self.state_send_photo = False
        self.amount_users = None
        self.last_winner = None

    def reset_values(self):
        self.state_photo = False
        self.state_in_game = False
        self.state_wait_votes = False
        self.users = None
        self.new_pair = None
        self.voters_dict = {}
        self.voters = []
        self.state_send_photo = False
        self.amount_users = None


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
        self.active_chats = {}
        self.time_end = {}
        self.storage = {}

    async def handle_updates(self, updates: list[Update]):
        for i in self.storage.keys():
            if time() - self.storage[i][0] > 10 and self.storage[i][1]:
                updates.append(
                    Update(
                        type="time_out",
                        object=UpdateObject(
                            chat_id=i,
                            id=-1,
                            body="time_out",
                        ),
                    )
                )
        for update in updates:
            if update.object.chat_id not in self.active_chats.keys():
                temp = SM()
                self.active_chats[update.object.chat_id] = temp
                this_chat = self.active_chats[update.object.chat_id]
            else:
                this_chat = self.active_chats[update.object.chat_id]
            if update.object.body == "Регистрация!":
                await self.command_registery(update)
            if update.object.body == "Загрузить фотографии!" or this_chat.state_photo:
                if not this_chat.state_in_game:
                    this_chat.state_photo = True
                    await self.command_download_photo(update, this_chat)
                else:
                    await self.app.store.vk_api.send_message(
                        Message(
                            chat_id=update.object.chat_id,
                            text=f"Нельзя загружать фотографии во время игры!",
                        )
                    )
            if update.object.body == "Начать игру!":
                if not this_chat.state_in_game:
                    this_chat.reset_values()
                    await self.command_start_game(update, this_chat)
                else:
                    await self.app.store.vk_api.send_message(
                        Message(chat_id=update.object.chat_id, text=f"Игра уже идет!")
                    )
            if update.object.body == "Остановить игру!":
                if this_chat.state_in_game:
                    await self.command_stop_game(this_chat, update)
                else:
                    await self.app.store.vk_api.send_message(
                        Message(
                            chat_id=update.object.chat_id,
                            text=f"Игровая сессия не запущена!",
                        )
                    )
            if update.object.body == "Последняя игра!":
                if not this_chat.state_in_game:
                    if this_chat.last_winner is not None:
                        await self.app.store.vk_api.send_message(
                            Message(
                                chat_id=update.object.chat_id,
                                text=f"Последний победитель: {this_chat.last_winner}",
                            )
                        )
                    else:
                        await self.app.store.vk_api.send_message(
                            Message(
                                chat_id=update.object.chat_id, text="Игр еще не было!"
                            )
                        )
                else:
                    await self.app.store.vk_api.send_message(
                        Message(
                            chat_id=update.object.chat_id,
                            text="Данная команда недоступна во время игры!",
                        )
                    )
            if update.object.body == "Моя статистика!":
                if not this_chat.state_in_game:
                    await self.app.database.connect()
                    async with self.app.database.session.begin() as session:
                        user_check_wins = select(
                            ParticipantsModel.__table__.c.wins,
                            ParticipantsModel.__table__.c.name
                        ).where(
                            ParticipantsModel.__table__.columns.chat_id
                            == update.object.chat_id,
                            ParticipantsModel.__table__.c.owner_id == update.object.id,
                        )
                        result = await session.execute(user_check_wins)
                        result = result.fetchall()
                        print(result)
                        await self.app.store.vk_api.send_message(
                            Message(
                                chat_id=update.object.chat_id,
                                text=f"Статистика игрока {result[-1][1]}:",
                            )
                        )
                        await self.app.store.vk_api.send_message(
                            Message(
                                chat_id=update.object.chat_id,
                                text=f"Кол-во побед: {result[-1][0]}",
                            )
                        )
                else:
                    await self.app.store.vk_api.send_message(
                        Message(
                            chat_id=update.object.chat_id,
                            text=f"Данная команда недоступна во время игры!",
                        )
                    )
            if this_chat.state_send_photo:
                await self.command_send_photo(update, this_chat)
            if this_chat.state_wait_votes:
                await self.command_write_answers(update, this_chat)
            if this_chat.state_in_game and (
                (not this_chat.state_wait_votes)
                or time() - self.storage[update.object.chat_id][0] > 10
            ):
                await self.command_send_preresult(update, this_chat)
                if self.check_users(this_chat):
                    if len(this_chat.users) == 1:
                        this_chat.last_winner = this_chat.users[-1][0]
                        await self.app.database.connect()
                        async with self.app.database.session.begin() as session:
                            user_new_win = (
                                refresh(ParticipantsModel.__table__)
                                .where(
                                    ParticipantsModel.__table__.c.name
                                    == this_chat.last_winner,
                                    ParticipantsModel.__table__.c.chat_id == update.object.chat_id,
                                )
                                .values(
                                    wins = ParticipantsModel.__table__.c.wins + 1,
                                )
                            )
                        await session.execute(user_new_win)
                        await session.commit()
                        await self.app.store.vk_api.send_message(
                            Message(
                                chat_id=update.object.chat_id,
                                text=f"Победил {this_chat.users[0][0]}!",
                            )
                        )
                    else:
                        await self.app.store.vk_api.send_message(
                            Message(
                                chat_id=update.object.chat_id, text=f"Никто не победил!"
                            )
                        )
                elif len(this_chat.users) > 1:
                    await self.command_send_photo(update, this_chat)
                    this_chat.state_send_photo = False

    async def command_registery(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            result = await app.store.vk_api.make_userlist(update.object.chat_id)
            for k, v in result:
                users_exists_select = select(
                    ParticipantsModel.__table__.c.chat_id,
                    ParticipantsModel.__table__.c.name,
                ).where(
                    ParticipantsModel.__table__.columns.chat_id
                    == update.object.chat_id,
                    ParticipantsModel.__table__.c.name == k,
                )
                result = await session.execute(users_exists_select)
                if not ((update.object.chat_id, k) in result.fetchall()):
                    new_user = ParticipantsModel(
                        name=k,
                        wins=0,
                        chat_id=update.object.chat_id,
                        owner_id=v,
                        photo_id=None,
                        access_key=None,
                    )
                    session.add(new_user)
            await session.commit()
            await self.app.store.vk_api.send_message(
                Message(
                    chat_id=update.object.chat_id, text="Регистрация прошла успешно!"
                )
            )

    def check_users(self, this_chat):
        if len(this_chat.users) <= 1:
            this_chat.state_send_photo = False
            this_chat.state_wait_votes = False
            this_chat.state_in_game = False
            return 1
        return 0

    async def command_download_photo(self, update, this_chat):
        if hasattr(update.object, "type") and update.object.type == "photo":
            await self.app.database.connect()
            async with self.app.database.session.begin() as session:
                users_add_photos = (
                    refresh(ParticipantsModel.__table__)
                    .where(
                        ParticipantsModel.__table__.c.owner_id
                        == update.object.owner_id,
                        ParticipantsModel.__table__.c.chat_id == update.object.chat_id,
                    )
                    .values(
                        photo_id=update.object.photo_id,
                        access_key=update.object.access_key,
                    )
                )
                await session.execute(users_add_photos)
                await session.commit()
                this_chat.state_photo = False
                await self.app.store.vk_api.send_message(
                    Message(
                        chat_id=update.object.chat_id,
                        text="Фотографии успешно загружены!",
                    )
                )

    async def command_start_game(self, update, this_chat):
        this_chat.users = await app.store.vk_api.proccess_start_game(
            update.object.chat_id
        )
        this_chat.amount_users = len(this_chat.users)
        if len(this_chat.users) == 0:
            await self.app.store.vk_api.send_message(
                Message(chat_id=update.object.chat_id, text="Вы не прошли регистрацию!")
            )
        else:
            for i in range(3, 0, -1):
                await self.app.store.vk_api.send_message(
                    Message(
                        chat_id=update.object.chat_id,
                        text=f"Игра начинается через {i}.",
                    )
                )
                sleep(1)
            await self.app.store.vk_api.send_message(
                Message(chat_id=update.object.chat_id, text=f"Поехали!")
            )
            this_chat.state_send_photo = True

    async def command_send_photo(self, update, this_chat):
        this_chat.new_pair = make_grid(this_chat.users)
        attach_pair = [i[1:] for i in this_chat.new_pair]
        await self.app.store.vk_api.send_photo(
            Attachment(
                chat_id=update.object.chat_id, attachment=attach_pair, text="Выбирай!"
            )
        )
        this_chat.state_in_game = True
        (
            this_chat.voters_dict[this_chat.new_pair[0]],
            this_chat.voters_dict[this_chat.new_pair[1]],
        ) = (0, 0)
        this_chat.state_wait_votes = True
        self.storage[update.object.chat_id] = [time(), this_chat.state_wait_votes]

    async def command_write_answers(self, update, this_chat):
        if update.object.id not in this_chat.voters:
            this_chat.state_send_photo = False
            if update.object.body == "1":
                this_chat.voters_dict[this_chat.new_pair[0]] += 1
                this_chat.voters.append(update.object.id)
                if len(this_chat.voters) == this_chat.amount_users:
                    this_chat.state_wait_votes = False
                    self.storage[update.object.chat_id][1] = this_chat.state_wait_votes
                    this_chat.voters = []
            elif update.object.body == "2":
                this_chat.voters_dict[this_chat.new_pair[1]] += 1
                this_chat.voters.append(update.object.id)
                if len(this_chat.voters) == this_chat.amount_users:
                    this_chat.state_wait_votes = False
                    self.storage[update.object.chat_id][1] = this_chat.state_wait_votes
                    this_chat.voters = []
            elif update.object.id == -1:
                this_chat.state_wait_votes = False
                self.storage[update.object.chat_id][1] = this_chat.state_wait_votes
                this_chat.voters = []
        elif update.object.id in this_chat.voters and update.object.body in ("1", "2"):
            await self.app.store.vk_api.send_message(
                Message(
                    chat_id=update.object.chat_id, text=f"Вы уже отдали свой голос!"
                )
            )

    async def command_send_preresult(self, update, this_chat):
        check = check_winner(this_chat.voters_dict, this_chat.new_pair)
        if check == 1:
            this_chat.users.remove(this_chat.new_pair[1])
            await self.app.store.vk_api.send_message(
                Message(
                    chat_id=update.object.chat_id,
                    text=f"И в текущем сражении победителем стал обладатель первой картинки",
                )
            )
        elif check == 2:
            this_chat.users.remove(this_chat.new_pair[0])
            await self.app.store.vk_api.send_message(
                Message(
                    chat_id=update.object.chat_id,
                    text=f"И в текущем сражении победителем стал обладатель второй картинки",
                )
            )
        elif not check:
            this_chat.users.remove(this_chat.new_pair[0])
            this_chat.users.remove(this_chat.new_pair[1])
            await self.app.store.vk_api.send_message(
                Message(
                    chat_id=update.object.chat_id,
                    text=f"Никто не победил - следовательно оба вылетают.",
                )
            )
        elif update.object.id == -1:
            this_chat.users.remove(choice(this_chat.new_pair))
            await self.app.store.vk_api.send_message(
                Message(
                    chat_id=update.object.chat_id,
                    text=f"Никто не проголосовал, поэтому победитель определяется случайным образом.",
                )
            )
        this_chat.state_send_photo = True

    async def command_stop_game(self, this_chat, update):
        await self.app.store.vk_api.send_message(
            Message(chat_id=update.object.chat_id, text="Оставшиеся пользователи:")
        )
        for i in this_chat.users:
            await self.app.store.vk_api.send_message(
                Message(chat_id=update.object.chat_id, text=f"{i[0]}")
            )
        this_chat.reset_values()
        self.storage[update.object.chat_id][1] = False
        await self.app.store.vk_api.send_message(
            Message(chat_id=update.object.chat_id, text=f"Игра остановлена!")
        )
