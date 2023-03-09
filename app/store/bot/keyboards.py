import json


def get_but(text, color):
    return {
        "action": {
            "type": "text",
            "payload": '{"button": "' + "1" + '"}',
            "label": f"{text}",
        },
        "color": f"{color}",
    }


keyboard_admin = {
    "one_time": True,
    "buttons": [
        [
            get_but("Регистрация!", "primary"),
            get_but("Загрузить фотографии!", "primary"),
        ],
        [
            get_but("Начать игру!", "primary"),
            get_but("Остановить игру!", "primary"),
        ],
        [
            get_but("Последняя игра!", "primary"),
            get_but("Следующий раунд!", "primary"),
        ],
        [
            get_but("Моя статистика!", "primary"),
            get_but("Статистика!", "primary"),
        ],
    ],
}

keyboard_admin = json.dumps(keyboard_admin, ensure_ascii=False).encode("utf-8")
keyboard_admin = str(keyboard_admin.decode("utf-8"))
