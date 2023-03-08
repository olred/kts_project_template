import os

from app.web.app import setup_app
from app.store.bot.bot_runner import run


if __name__ == "__main__":
    setup_app(
        config_path=os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "config.yml"
        )
    )
    run()
