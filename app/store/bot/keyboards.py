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


keyboard = {
    "one_time": False,
    "buttons": [
        [
            get_but("Регистрация!", "primary"),
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

keyboard = json.dumps(keyboard, ensure_ascii=False).encode("utf-8")
keyboard = str(keyboard.decode("utf-8"))
