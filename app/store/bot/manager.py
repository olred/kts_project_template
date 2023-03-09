import asyncio
import typing
from logging import getLogger
from random import choice

from sqlalchemy import insert
from sqlalchemy.sql import select, update as refresh, delete

from app.store.bot.keyboards import keyboard_admin
from app.store.bot.lexicon import (
    commands_for_users,
    commands_for_admins,
    lexicon_for_messages,
)
from app.store.bot.services import make_grid, check_winner, check_kicked
from app.web.app import app
from app.store.models.model import ParticipantsModel, GameModel, GameSession

if typing.TYPE_CHECKING:
    from app.web.app import Application


class BotManager:
    def __init__(
        self, in_queue, out_queue, app: "Application", concurrent_workers
    ):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")
        self.active_chats = {}
        self._tasks: typing.List[asyncio.Task] = []
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.concurrent_workerks = concurrent_workers
        self.time_end = {}
        self.storage = {}
        self.reader = open(
            "/home/olred/PycharmProjects/kts_project_template/app/store/bot/admins_id.txt",
            "r",
            encoding="utf-8",
        )
        self.actions = {
            "chat_kick_user": self.command_kick,
            "chat_invite_user": self.command_invite,
        }
        self.commands = {
            f"{lexicon_for_messages['ID_GROUP']} Регистрация!": self.command_registery,
            f"{lexicon_for_messages['ID_GROUP']} Начать игру!": self.command_start_game,
            f"{lexicon_for_messages['ID_GROUP']} Остановить игру!": self.command_stop_game,
            f"{lexicon_for_messages['ID_GROUP']} Последняя игра!": self.command_last_game,
            f"{lexicon_for_messages['ID_GROUP']} Моя статистика!": self.command_my_statistic,
            f"Команды!": self.command_list_of_commands,
            f"{lexicon_for_messages['ID_GROUP']} Следующий раунд!": self.command_next_round,
            f"{lexicon_for_messages['ID_GROUP']} Статистика!": self.command_general_statistic,
        }

    async def handle_updates(self, update):
        if (
            hasattr(update.object, "member_id")
            and update.object.member_id == -207946988
            and update.object.type == "chat_invite_user"
        ):
            await self.actions.get(update.object.type)(update)
        elif (
            update.object.type in self.actions.keys()
            and not update.object.type == "chat_invite_user"
        ):
            await self.actions.get(update.object.type)(update)
        game = await self.get_game(update)
        users = await self.get_users(update)
        self.reader = list(map(int, self.reader))
        if update.object.body in self.commands:
            await self.commands[update.object.body](update, game)
        if (
            update.object.body
            == f"{lexicon_for_messages['ID_GROUP']} Загрузить фотографии!"
            or game["state_photo"]
        ):
            if len(users) == 0:
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["NO_REG"],
                    )
                )
            else:
                if not game["state_in_game"]:
                    if not game["state_photo"]:
                        await self.set_state_photo(update, True)
                    else:
                        await self.command_download_photo(update)
                else:
                    self.out_queue.put_nowait(
                        (
                            "message",
                            update.object.chat_id,
                            lexicon_for_messages["DUR_GAME"],
                        )
                    )
        if (
            len(update.object.body.split()) == 2
            and f"{lexicon_for_messages['ID_GROUP']} Исключить"
            in update.object.body.split()
        ):
            await self.command_kick_from_game(
                update.object.body.split()[1], update, game
            )

        if game["state_send_photo"]:
            await self.command_send_photo(update, game)
        if game["state_wait_votes"]:
            await self.command_write_answers(update, game)
        if game["state_in_game"] and ((not game["state_wait_votes"])):
            await self.command_send_preresult(update, game)
            if self.check_users(game):
                game["state_in_game"] = False
                game["state_send_photo"] = False
                await self.reset_all_states(update)
                if len(game["users"]["participants"]) == 1:
                    game["last_winner"] = list(
                        game["users"]["participants"][-1].keys()
                    )[0]
                    await self.set_last_winner(update, game["last_winner"])
                    self.out_queue.put_nowait(
                        (
                            "message",
                            update.object.chat_id,
                            f"{lexicon_for_messages['WINNER']} {game['last_winner']}",
                        )
                    )
                    game["kicked_users"]["kicked"] = []
                    await self.set_kicked(update, game["kicked_users"], game)
                    await self.new_win(update, game)
                else:
                    game["kicked_users"]["kicked"] = []
                    await self.set_kicked(update, game["kicked_users"], game)
                    self.out_queue.put_nowait(
                        (
                            "message",
                            update.object.chat_id,
                            lexicon_for_messages["NO_WINNERS"],
                        )
                    )
            elif len(game["users"]["participants"]) > 1:
                await self.command_send_photo(update, game)

    @staticmethod
    def post_init(game):
        game["users"] = {}
        game["new_pair"] = {}
        game["voters"] = {}

    async def command_registery(self, update, game):
        if not game["state_in_game"]:
            await self.app.database.connect()
            async with self.app.database.session.begin() as session:
                result = await app.store.vk_api.make_userlist(
                    update.object.chat_id, self.app
                )
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
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["SUCC_REG"],
                    )
                )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["DUR_GAME"],
                )
            )

    async def command_next_round(self, update, game):
        if game["state_in_game"]:
            game["state_wait_votes"] = False
            game["voters"]["already_voted"] = []
            await self.set_state_wait_votes(update, game["state_wait_votes"])
            await self.set_voters(update, [], game)
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["GAME_NO_EXIST"],
                )
            )

    async def command_list_of_commands(self, update, game):
        if not game["state_in_game"]:
            if update.object.id in self.reader:
                result = ""
                for i in commands_for_users.items():
                    result += f"{i[0]}: {i[1]}%0A"
                for i in commands_for_admins.items():
                    result += f"{i[0]}: {i[1]}%0A"
                self.out_queue.put_nowait(
                    (
                        "keyboard",
                        update.object.chat_id,
                        lexicon_for_messages["COMMANDS"],
                        keyboard_admin,
                    )
                )
            else:
                result = ""
                for i in commands_for_users.items():
                    result += f"{i[0]}: {i[1]}%0A"
                self.out_queue.put_nowait(
                    (
                        "keyboard",
                        update.object.chat_id,
                        lexicon_for_messages["COMMANDS"],
                        keyboard_user,
                    )
                )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["DUR_GAME"],
                )
            )

    async def command_my_statistic(self, update, game):
        if not game["state_in_game"]:
            result = await self.get_statistics(update)
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    f"{lexicon_for_messages['STATISTIC_PLAYER']} {result[-1][1]}:%0A{lexicon_for_messages['AMOUNT_WINS']}: {result[-1][0]}",
                )
            )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["DUR_GAME"],
                )
            )

    async def command_general_statistic(self, update, game):
        if not game["state_in_game"]:
            if update.object.id in self.reader:
                result = await self.get_all_statistics(update)
                for i in result:
                    self.out_queue.put_nowait(
                        (
                            "message",
                            update.object.chat_id,
                            f"{lexicon_for_messages['STATISTIC_PLAYER']} {i[1]}:%0A{lexicon_for_messages['AMOUNT_WINS']}: {i[0]}",
                        )
                    )
            else:
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["ADMIN_COMMAND"],
                    )
                )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["DUR_GAME"],
                )
            )

    async def command_last_game(self, update, game):
        if not game["state_in_game"]:
            if game["last_winner"] is not None:
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        f"{lexicon_for_messages['LAST_WINNER']}: {game['last_winner']}",
                    )
                )
            else:
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["NO_LAST_WINNER"],
                    )
                )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["DUR_GAME"],
                )
            )

    async def get_game(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            game_state = select(GameModel.__table__).where(
                GameModel.__table__.c.chat_id == update.object.chat_id
            )
            temp = await session.execute(game_state)
            temp = temp.fetchall()
        result = {
            "chat_id": temp[0][1],
            "users": temp[0][2],
            "state_photo": temp[0][3],
            "state_in_game": temp[0][4],
            "state_wait_votes": temp[0][5],
            "new_pair": temp[0][6],
            "first_votes": temp[0][7],
            "second_votes": temp[0][8],
            "state_send_photo": temp[0][9],
            "voters": temp[0][10],
            "amount_users": temp[0][11],
            "last_winner": temp[0][12],
            "kicked_users": temp[0][13],
        }
        return result

    async def get_users(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            users_info = select(ParticipantsModel.__table__).where(
                ParticipantsModel.__table__.c.chat_id == update.object.chat_id
            )
            result = await session.execute(users_info)
        return result.fetchall()

    async def set_last_winner(self, update, value):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_state_photo = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(last_winner=value)
            )
            await session.execute(query_state_photo)
        await session.commit()

    async def set_state_photo(self, update, value):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_state_photo = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(state_photo=value)
            )
            await session.execute(query_state_photo)
        await session.commit()

    async def set_state_send_photo(self, update, value):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_state_send_photo = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(state_send_photo=value)
            )
            await session.execute(query_state_send_photo)
        await session.commit()

    async def set_amount_users(self, update, amount):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_amount_users = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(amount_users=amount)
            )
            await session.execute(query_amount_users)
        await session.commit()

    async def set_participants(self, chat_id, users):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            users_write_in_game = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == chat_id,
                )
                .values(users=users)
            )
            await session.execute(users_write_in_game)
        await session.commit()

    async def set_new_pair(self, update, new_pair):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_new_pair = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(new_pair=new_pair)
            )
            await session.execute(query_new_pair)
        await session.commit()

    async def set_state_in_game(self, update, value):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_state_in_game = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(state_in_game=value)
            )
            await session.execute(query_state_in_game)
        await session.commit()

    async def set_state_wait_votes(self, update, value):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_state_wait_votes = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(state_wait_votes=value)
            )
            await session.execute(query_state_wait_votes)
        await session.commit()

    async def set_first_votes(self, update, value):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_first_votes = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(first_votes=value)
            )
            await session.execute(query_first_votes)
        await session.commit()

    async def set_second_votes(self, update, value):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_second_votes = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(second_votes=value)
            )
            await session.execute(query_second_votes)
        await session.commit()

    async def set_voters(self, update, value, game):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            if value is None:
                game["voters"]["already_voted"] = []
            query_second_votes = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(voters=game["voters"])
            )
            await session.execute(query_second_votes)
        await session.commit()

    async def set_kicked(self, update, value, game):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            users_kicked_from_game = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(kicked_users=value)
            )
            await session.execute(users_kicked_from_game)
        await session.commit()

    async def reset_all_states(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            query_state_photo = (
                refresh(GameModel.__table__)
                .where(
                    GameModel.__table__.c.chat_id == update.object.chat_id,
                )
                .values(
                    users=None,
                    state_in_game=None,
                    state_wait_votes=None,
                    new_pair=None,
                    first_votes=0,
                    second_votes=0,
                    state_send_photo=None,
                    amount_users=None,
                    voters=None,
                )
            )
            await session.execute(query_state_photo)
        await session.commit()

    async def new_win(self, update, game):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            user_new_win = (
                refresh(ParticipantsModel.__table__)
                .where(
                    ParticipantsModel.__table__.c.name == game["last_winner"],
                    ParticipantsModel.__table__.c.chat_id
                    == update.object.chat_id,
                )
                .values(
                    wins=ParticipantsModel.__table__.c.wins + 1,
                )
            )
            await session.execute(user_new_win)
        await session.commit()

    async def get_statistics(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            user_check_wins = select(
                ParticipantsModel.__table__.c.wins,
                ParticipantsModel.__table__.c.name,
            ).where(
                ParticipantsModel.__table__.columns.chat_id
                == update.object.chat_id,
                ParticipantsModel.__table__.c.owner_id == update.object.id,
            )
            result = await session.execute(user_check_wins)
        return result.fetchall()

    async def get_all_statistics(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            user_check_wins = select(
                ParticipantsModel.__table__.c.wins,
                ParticipantsModel.__table__.c.name,
            ).where(
                ParticipantsModel.__table__.columns.chat_id
                == update.object.chat_id,
            )
            result = await session.execute(user_check_wins)
        return result.fetchall()

    async def command_kick(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            user_check_wins = delete(ParticipantsModel.__table__).where(
                ParticipantsModel.__table__.columns.chat_id
                == update.object.chat_id,
                ParticipantsModel.__table__.c.owner_id == update.object.id,
            )
            await session.execute(user_check_wins)
        await session.commit()

    async def command_invite(self, update):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            user_newsession_wins = insert(GameSession.__table__).values(
                chat_id=update.object.chat_id,
            )
            await session.execute(user_newsession_wins)
            user_newchat_wins = insert(GameModel.__table__).values(
                chat_id=update.object.chat_id,
            )
            await session.execute(user_newchat_wins)
        await session.commit()
        self.out_queue.put_nowait(
            (
                "message",
                update.object.chat_id,
                lexicon_for_messages["WELCOME_PHRASE"],
            )
        )

    def check_users(self, game):
        if len(game["users"]["participants"]) <= 1:
            return 1
        return 0

    async def command_download_photo(self, update):
        if hasattr(update.object, "type") and update.object.type == "photo":
            await self.app.database.connect()
            async with self.app.database.session.begin() as session:
                users_add_photos = (
                    refresh(ParticipantsModel.__table__)
                    .where(
                        ParticipantsModel.__table__.c.owner_id
                        == update.object.owner_id,
                        ParticipantsModel.__table__.c.chat_id
                        == update.object.chat_id,
                    )
                    .values(
                        photo_id=update.object.photo_id,
                        access_key=update.object.access_key,
                    )
                )
                await self.set_state_photo(update, False)
                await session.execute(users_add_photos)
                await session.commit()

                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["SUCC_PHOTO"],
                    )
                )

    async def proccess_start_game(self, chat_id):
        await self.app.database.connect()
        async with self.app.database.session.begin() as session:
            users_exists_select = select(
                ParticipantsModel.__table__.c.name,
                ParticipantsModel.__table__.c.owner_id,
                ParticipantsModel.__table__.c.photo_id,
                ParticipantsModel.__table__.c.access_key,
            ).where(ParticipantsModel.__table__.c.chat_id == chat_id)
            temp = await session.execute(users_exists_select)
            temp = temp.fetchall()
            result = {"participants": []}
            for i in temp:
                result["participants"] = result.get("participants", []) + [
                    {i[0]: [i[1], i[2], i[3]]}
                ]
            return result

    async def command_kick_from_game(self, kicked_name, update, game):
        if not game["state_in_game"]:
            if update.object.id in self.reader:
                user_name = kicked_name[kicked_name.find("|") + 1 : -1]
                if game["kicked_users"] is None:
                    game["kicked_users"] = {}
                game["kicked_users"]["kicked"] = game["kicked_users"].get(
                    "kicked", []
                ) + [user_name]
                await self.set_kicked(update, game["kicked_users"], game)
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["USER_KICKED"],
                    )
                )
            else:
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["ADMIN_COMMAND"],
                    )
                )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["DUR_GAME"],
                )
            )

    async def command_start_game(self, update, game):
        if not game["state_in_game"]:
            self.post_init(game)
            await self.reset_all_states(update)
            game["users"] = await self.proccess_start_game(
                update.object.chat_id
            )
            if game["kicked_users"] is None:
                game["kicked_users"] = {}
                game["kicked_users"]["kicked"] = []
                await self.set_kicked(update, game["kicked_users"], game)
            game["users"] = check_kicked(
                game["kicked_users"]["kicked"], game["users"]
            )
            await self.set_participants(update.object.chat_id, game["users"])
            if len(
                list(
                    filter(
                        lambda x: all(
                            j is not None for i in x.values() for j in i
                        ),
                        game["users"]["participants"],
                    )
                )
            ) == len(game["users"]["participants"]):
                game["amount_users"] = len(game["users"]["participants"])
                await self.set_amount_users(update, game["amount_users"])
                if len(game["users"]["participants"]) == 0:
                    self.out_queue.put_nowait(
                        (
                            "message",
                            update.object.chat_id,
                            lexicon_for_messages["NO_REG"],
                        )
                    )
                elif len(game["users"]["participants"]) == 1:
                    self.out_queue.put_nowait(
                        (
                            "message",
                            update.object.chat_id,
                            lexicon_for_messages["LITTLE_PEOPLE"],
                        )
                    )
                else:
                    for i in range(3, 0, -1):
                        self.out_queue.put_nowait(
                            (
                                "message",
                                update.object.chat_id,
                                f"{lexicon_for_messages['START_GAME']} {i}.",
                            )
                        )
                    self.out_queue.put_nowait(
                        (
                            "message",
                            update.object.chat_id,
                            lexicon_for_messages["LETS_GO"],
                        )
                    )
                    await self.set_state_send_photo(update, True)
                    game["state_send_photo"] = True
            else:
                self.out_queue.put_nowait(
                    (
                        "message",
                        update.object.chat_id,
                        lexicon_for_messages["NOT_ENOUGH_PHOTO"],
                    )
                )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["GAME_GO"],
                )
            )

    async def command_send_photo(self, update, game):
        game["new_pair"] = make_grid(game["users"]["participants"])
        await self.set_new_pair(update, game["new_pair"])
        self.out_queue.put_nowait(
            (
                "photo",
                update.object.chat_id,
                lexicon_for_messages["CHOOSE"],
                [
                    list(game["new_pair"][0].values())[0],
                    list(game["new_pair"][1].values())[0],
                ],
            )
        )
        game["state_in_game"] = True
        await self.set_state_in_game(update, game["state_in_game"])
        game["first_votes"], game["second_votes"] = 0, 0
        await self.set_first_votes(update, game["first_votes"])
        await self.set_second_votes(update, game["second_votes"])
        game["state_wait_votes"] = True
        await self.set_state_wait_votes(update, game["state_wait_votes"])
        game["state_send_photo"] = False
        await self.set_state_send_photo(update, game["state_send_photo"])

    async def command_write_answers(self, update, game):
        if game["voters"] is None:
            game["voters"] = {}
        if update.object.id not in game["voters"].get("already_voted", []):
            game["state_send_photo"] = False
            await self.set_state_send_photo(update, game["state_send_photo"])
            if update.object.body == "1":
                game["first_votes"] += 1
                await self.set_first_votes(update, game["first_votes"])
                game["voters"]["already_voted"] = game["voters"].get(
                    "already_voted", []
                ) + [update.object.id]
                await self.set_voters(update, update.object.id, game)
                if len(game["voters"]["already_voted"]) == game["amount_users"]:
                    game["state_wait_votes"] = False
                    await self.set_state_wait_votes(update, False)
                    game["voters"]["already_voted"] = []
                    await self.set_voters(update, [], game)

            elif update.object.body == "2":
                game["second_votes"] += 1
                await self.set_second_votes(update, game["second_votes"])
                game["voters"]["already_voted"] = game["voters"].get(
                    "already_voted", []
                ) + [update.object.id]
                await self.set_voters(update, update.object.id, game)
                if len(game["voters"]["already_voted"]) == game["amount_users"]:
                    game["state_wait_votes"] = False
                    await self.set_state_wait_votes(
                        update, game["state_wait_votes"]
                    )
                    game["voters"]["already_voted"] = []
                    await self.set_voters(update, [], game)
            elif update.object.id == -1:
                game["state_wait_votes"] = False
                await self.set_state_wait_votes(update, False)
                game["voters"]["already_voted"] = []
                await self.set_voters(update, [], game)
        elif update.object.id in game["voters"][
            "already_voted"
        ] and update.object.body in (
            "1",
            "2",
        ):
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["ALR_VOTED"],
                )
            )

    async def command_send_preresult(self, update, game):
        check = check_winner(game)
        if check == 1:
            game["users"]["participants"].remove(game["new_pair"][1])
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["FIRST_WIN"],
                )
            )
        elif check == 2:
            game["users"]["participants"].remove(game["new_pair"][0])
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["SECOND_WIN"],
                )
            )
        elif not check:
            game["users"]["participants"].remove(game["new_pair"][0])
            game["users"]["participants"].remove(game["new_pair"][1])
            self.out_queue.put_nowait(
                ("message", update.object.chat_id, lexicon_for_messages["DRAW"])
            )
        elif update.object.id == -1:
            game["users"]["participants"].remove(
                choice(
                    game["new_pair"]["first_partic"]
                    + game["new_pair"]["second_partic"]
                )
            )
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["RANDOM_WIN"],
                )
            )
        game["state_send_photo"] = True
        await self.set_participants(update.object.chat_id, game["users"])
        await self.set_state_send_photo(update, True)

    async def command_stop_game(self, update, game):
        if game["state_in_game"]:
            game["kicked_users"]["kicked"] = []
            await self.set_kicked(update, game["kicked_users"], game)
            game["state_in_game"] = False
            await self.set_state_in_game(update, game["state_in_game"])
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["REMAIN"],
                )
            )
            for i in game["users"]["participants"]:
                self.out_queue.put_nowait(
                    ("message", update.object.chat_id, f"{list(i.keys())[0]}")
                )
            await self.reset_all_states(update)
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["GAME_STOP"],
                )
            )
        else:
            self.out_queue.put_nowait(
                (
                    "message",
                    update.object.chat_id,
                    lexicon_for_messages["GAME_NO_EXIST"],
                )
            )

    async def _worker(self):
        while True:
            try:
                upd = await self.in_queue.get()
                await self.handle_updates(upd)
            finally:
                self.in_queue.task_done()

    async def start(self):
        for _ in range(self.concurrent_workerks):
            asyncio.create_task(self._worker())

    async def stop(self):
        await self.in_queue.join()
        self.reader.close()
        for t in self._tasks:
            t.cancel()
