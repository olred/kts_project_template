from aiohttp.web_app import Application
from aiohttp_cors import CorsConfig

__all__ = ("register_urls",)


def register_urls(application: Application, cors: CorsConfig):
    import app.users.urls

    app.users.urls.register_urls(application, cors)
