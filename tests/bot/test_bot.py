from app.store.models.model import ParticipantsModel
from app.store.vk_api.dataclasses import Message, Update, UpdateObject, UpdatePhoto
from sqlalchemy import select

class TestManager:
    async def test_registration_command(self, store):
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Регистрация!",
                        type="test_type"
                    ),
                )
            ]
        )
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert store.vk_api.make_userlist.call_count == 1
        assert message.chat_id == 1
        assert message.text == "Регистрация прошла успешно!"


    async def test_no_auth_download_command(self, store):
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Загрузить фотографии!",
                        type="test_type"
                    ),
                )
            ]
        )
        # assert store.vk_api.send_message.call_count == 1
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == "Вы не прошли регистрацию!"


    async def test_auth_download_command(self, store, db_session, cli):
        async with db_session.begin() as session:
            new_user = ParticipantsModel(
                name="olred",
                wins=0,
                chat_id=1,
                owner_id=1,
                photo_id=None,
                access_key=None,
            )
            session.add(new_user)
        await session.commit()
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Загрузить фотографии!",
                        type="test_type"
                    ),
                )
            ]
        )
        await store.bots_manager.handle_updates(
            updates=[
                Update(
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
            ]
        )
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == "Фотографии успешно загружены!"


    async def test_no_auth_start_command(self, store):
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Начать игру!",
                        type="test_type"
                    ),
                )
            ]
        )
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == "Вы не прошли регистрацию!"

    async def test_stop_no_game_command(self, store):
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Остановить игру!",
                        type="test_type"
                    ),
                )
            ]
        )
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == "Игровая сессия не запущена!"


    async def test_statistics_command(self, store, db_session, cli):
        async with db_session.begin() as session:
            new_user = ParticipantsModel(
                name="olred",
                wins=2,
                chat_id=1,
                owner_id=1,
                photo_id=1,
                access_key="dasda",
            )
            session.add(new_user)
        await session.commit()
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Моя статистика!",
                        type="test_type"
                    ),
                )
            ]
        )
        message: Message = store.vk_api.send_message.mock_calls[-1].args[0]
        assert message.chat_id == 1
        assert message.text == "Статистика игрока olred:%0AКол-во побед: 2"



    async def test_left_command(self, store, db_session, cli):
        async with db_session.begin() as session:
            new_user = ParticipantsModel(
                name="olred",
                wins=0,
                chat_id=1,
                owner_id=1,
                photo_id=None,
                access_key=None,
            )
            session.add(new_user)
        await session.commit()
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="",
                        type="chat_kick_user"
                    ),
                )
            ]
        )
        async with db_session.begin() as session:
            users_exists_select = select(
                ParticipantsModel.__table__.c.chat_id,
                ParticipantsModel.__table__.c.name,
            ).where(
                ParticipantsModel.__table__.columns.chat_id
                == 1,
                ParticipantsModel.__table__.c.name == "olred",
            )
            result = await session.execute(users_exists_select)
            assert len(result.fetchall()) == 0
    async def test_in_game_commands(self, store, db_session, cli):
        async with db_session.begin() as session:
            for i in range(2):
                new_user = ParticipantsModel(
                    name=f"olred{i}",
                    wins=0,
                    chat_id=1,
                    owner_id=1+i,
                    photo_id=1,
                    access_key="dasda",
                )
                session.add(new_user)
            await session.commit()
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Начать игру!",
                        type="test_type"
                    ),
                )
            ]
        )
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Загрузить фотографии!",
                        type="test_type"
                    ),
                )
            ]
        )
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Начать игру!",
                        type="test_type"
                    ),
                )
            ]
        )
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Моя статистика!",
                        type="test_type"
                    ),
                )
            ]
        )
        await store.bots_manager.handle_updates(
            updates=[
                Update(
                    type="message_new",
                    object=UpdateObject(
                        id=1,
                        chat_id=1,
                        body="Остановить игру!",
                        type="test_type"
                    ),
                )
            ]
        )
        message_1: Message = store.vk_api.send_message.mock_calls[3].args[0]
        message_2: Message = store.vk_api.send_message.mock_calls[-1].args[0]
        message_3: Message = store.vk_api.send_message.mock_calls[4].args[0]
        message_4: Message = store.vk_api.send_message.mock_calls[5].args[0]
        message_5: Message = store.vk_api.send_message.mock_calls[6].args[0]
        assert message_2.chat_id == 1
        assert message_1.text == "Поехали!"
        assert message_2.text == "Игра остановлена!"
        assert message_3.text == "Нельзя загружать фотографии во время игры!"
        assert message_4.text == "Игра уже идет!"
        assert message_5.text == "Данная команда недоступна во время игры!"


