import asyncio
import datetime


from app.bot_vk import Bot


def run():
    loop = asyncio.get_event_loop()
    bot = Bot(100)
    try:
        print("Bot has been started")
        loop.create_task(bot.start())
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nstopping", datetime.datetime.now())
        loop.run_until_complete(bot.stop())
        print("Bot has been stopped", datetime.datetime.now())
