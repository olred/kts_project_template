from app.store.models.model import ParticipantsModel, GameModel
from app.store.bot.lexicon import lexicon_for_messages
from app.store.vk_api.dataclasses import (
    Message,
    Update,
    UpdateObject,
    UpdatePhoto,
)
from sqlalchemy import select


class TestManager:
    async def test_registration_command(self, store, cli, create_base):
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=1, chat_id=1, body="Регистрация!", type="test_type"
            ),
        )
        await store.bot_manager.handle_updates(upd)
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
                break
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert store.vk_api.make_userlist.call_count == 1
        assert message.chat_id == 1
        assert message.text == lexicon_for_messages["SUCC_REG"]

    async def test_no_auth_download_command(
        self, store, cli, no_auth_create_base
    ):
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=1,
                chat_id=1,
                body="Загрузить фотографии!",
                type="test_type",
            ),
        )
        await store.bot_manager.handle_updates(upd)
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
                break
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == lexicon_for_messages["NO_REG"]

    async def test_auth_download_command(self, store, cli, create_base):
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=1,
                chat_id=1,
                body="Загрузить фотографии!",
                type="test_type",
            ),
        )
        await store.bot_manager.handle_updates(upd)
        upd = Update(
            type="message_new",
            object=UpdatePhoto(
                id=1,
                chat_id=1,
                body="",
                type="photo",
                owner_id=1,
                photo_id=1,
                access_key="1",
            ),
        )
        await store.bot_manager.handle_updates(upd)
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
                break
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == lexicon_for_messages["SUCC_PHOTO"]

    async def test_no_auth_start_command(self, store, cli, no_auth_create_base):
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=1, chat_id=1, body="Начать игру!", type="test_type"
            ),
        )
        await store.bot_manager.handle_updates(upd)
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
                break
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == lexicon_for_messages["NO_REG"]

    async def test_stop_no_game_command(self, store, cli, create_base):
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=1,
                chat_id=1,
                body="Остановить игру!",
                type="test_type",
            ),
        )
        await store.bot_manager.handle_updates(upd)
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
                break
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == lexicon_for_messages["GAME_NO_EXIST"]

    async def test_statistics_command(self, store, cli, create_base):
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=1,
                chat_id=1,
                body="Моя статистика!",
                type="test_type",
            ),
        )
        await store.bot_manager.handle_updates(upd)
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
                break
        message: Message = store.vk_api.send_message.mock_calls[-1].args[0]
        assert message.chat_id == 1
        assert (
            message.text
            == f"{lexicon_for_messages['STATISTIC_PLAYER']} olred:%0A{lexicon_for_messages['AMOUNT_WINS']}: 0"
        )

    async def test_left_command(
        self, store, cli, create_base, db_session, connection
    ):
        await store.bot_manager.handle_updates(
            Update(
                type="message_new",
                object=UpdateObject(
                    id=1, chat_id=1, body="", type="chat_kick_user"
                ),
            )
        )
        async with db_session.begin() as session:
            users_exists_select = select(
                ParticipantsModel.__table__.c.chat_id,
                ParticipantsModel.__table__.c.name,
            ).where(
                ParticipantsModel.__table__.columns.chat_id == 1,
                ParticipantsModel.__table__.c.name == "olred",
            )
            result = await session.execute(users_exists_select)
            assert len(result.fetchall()) == 0

    async def test_statistics_admin_command(
        self, store, connection, db_session, cli, no_auth_create_base
    ):
        async with db_session.begin() as session:
            for i in range(2):
                new_user = ParticipantsModel(
                    name=f"olred{i}",
                    wins=0,
                    chat_id=1,
                    owner_id=582423336 + i,
                    photo_id=1,
                    access_key="dasda",
                )
                session.add(new_user)
            await session.commit()
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=582423336, chat_id=1, body="Статистика!", type="test_type"
            ),
        )
        await store.bot_manager.handle_updates(upd)
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
        message_1: Message = store.vk_api.send_message.mock_calls[0].args[0]
        message_2: Message = store.vk_api.send_message.mock_calls[1].args[0]
        assert message_1.chat_id == 1
        assert (
            message_1.text
            == f"{lexicon_for_messages['STATISTIC_PLAYER']} olred0:%0A{lexicon_for_messages['AMOUNT_WINS']}: 0"
        )
        assert (
            message_2.text
            == f"{lexicon_for_messages['STATISTIC_PLAYER']} olred1:%0A{lexicon_for_messages['AMOUNT_WINS']}: 0"
        )

    async def test_in_game_commands(
        self, store, connection, db_session, cli, no_auth_create_base
    ):
        async with db_session.begin() as session:
            for i in range(2):
                new_user = ParticipantsModel(
                    name=f"olred{i}",
                    wins=0,
                    chat_id=1,
                    owner_id=1 + i,
                    photo_id=1,
                    access_key="dasda",
                )
                session.add(new_user)
            await session.commit()
        await store.bot_manager.handle_updates(
            Update(
                type="message_new",
                object=UpdateObject(
                    id=1, chat_id=1, body="Начать игру!", type="test_type"
                ),
            )
        )
        await store.bot_manager.handle_updates(
            Update(
                type="message_new",
                object=UpdateObject(
                    id=1,
                    chat_id=1,
                    body="Загрузить фотографии!",
                    type="test_type",
                ),
            )
        )
        await store.bot_manager.handle_updates(
            Update(
                type="message_new",
                object=UpdateObject(
                    id=1, chat_id=1, body="Начать игру!", type="test_type"
                ),
            )
        )
        await store.bot_manager.handle_updates(
            Update(
                type="message_new",
                object=UpdateObject(
                    id=1,
                    chat_id=1,
                    body="Моя статистика!",
                    type="test_type",
                ),
            )
        )
        await store.bot_manager.handle_updates(
            Update(
                type="message_new",
                object=UpdateObject(
                    id=1,
                    chat_id=1,
                    body="Остановить игру!",
                    type="test_type",
                ),
            )
        )
        while not store.out_queue.empty():
            try:
                upd = await store.out_queue.get()
                await store.vk_sender.send_vk(upd)
            finally:
                store.out_queue.task_done()
        message_1: Message = store.vk_api.send_message.mock_calls[3].args[0]
        message_2: Message = store.vk_api.send_message.mock_calls[-1].args[0]
        message_3: Message = store.vk_api.send_message.mock_calls[4].args[0]
        message_4: Message = store.vk_api.send_message.mock_calls[5].args[0]
        message_5: Message = store.vk_api.send_message.mock_calls[6].args[0]
        assert message_2.chat_id == 1
        assert message_1.text == lexicon_for_messages["LETS_GO"]
        assert message_2.text == lexicon_for_messages["GAME_STOP"]
        assert message_3.text == lexicon_for_messages["DUR_GAME"]
        assert message_4.text == lexicon_for_messages["GAME_GO"]
        assert message_5.text == lexicon_for_messages["DUR_GAME"]

    async def test_kick_from_game_admin_command(
        self, store, connection, db_session, cli, no_auth_create_base
    ):
        async with db_session.begin() as session:
            for i in range(2):
                new_user = ParticipantsModel(
                    name=f"@olred{i}",
                    wins=0,
                    chat_id=1,
                    owner_id=1 + i,
                    photo_id=1,
                    access_key="dasda",
                )
                session.add(new_user)
            await session.commit()
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=582423336,
                chat_id=1,
                body="Исключить @olred0",
                type="test_type",
            ),
        )
        await store.bot_manager.handle_updates(upd)
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=582423336, chat_id=1, body="Начать игру!", type="test_type"
            ),
        )
        await store.bot_manager.handle_updates(upd)
        upd = Update(
            type="message_new",
            object=UpdateObject(
                id=582423336,
                chat_id=1,
                body="Остановить игру!",
                type="test_type",
            ),
        )
        async with db_session.begin() as session:
            users_exists_select = select(GameModel.__table__.c.users)
            result = await session.execute(users_exists_select)
            massiv_keys = []
            for i in result.fetchall()[-1][-1]["participants"]:
                key_value = list(i.keys())[-1]
                if key_value != "@olred0":
                    massiv_keys.append(key_value)
            assert "@olred0" not in massiv_keys
