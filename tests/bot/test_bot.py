from app.store.models.model import ParticipantsModel
from app.store.vk_api.dataclasses import Message, Update, UpdateObject, UpdatePhoto


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
                    ),
                )
            ]
        )
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
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
        # assert store.vk_api.send_message.call_count > 0
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
                    ),
                )
            ]
        )
        message: Message = store.vk_api.send_message.mock_calls[0].args[0]
        assert message.chat_id == 1
        assert message.text == "Игровая сессия не запущена!"

    async def test_auth_start_command(self, store, db_session, cli):
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
                    ),
                )
            ]
        )

        message: Message = store.vk_api.send_message.mock_calls[3].args[0]
        assert message.chat_id == 1
        assert message.text == "Поехали!"





    async def test_stop_in_game_command(self, store, db_session, cli):
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
                    ),
                )
            ]
        )

        message: Message = store.vk_api.send_message.mock_calls[-1].args[0]
        assert message.chat_id == 1
        assert message.text == "Игра остановлена!"