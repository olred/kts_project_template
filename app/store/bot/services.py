from random import choice


def make_grid(data_users: list):
    participant_1 = None
    participant_2 = None
    while participant_1 == participant_2:
        participant_1 = choice(data_users)
        participant_2 = choice(data_users)
    return [participant_1, participant_2]


def check_winner(game: dict, pair: list):
    if game[pair[0]] > game[pair[1]]:
        return 1
    if game[pair[0]] < game[pair[1]]:
        return 2
    return 0
