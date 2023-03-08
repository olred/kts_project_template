from random import choice


def make_grid(data_users: list):
    participant_1 = None
    participant_2 = None
    while participant_1 == participant_2:
        participant_1 = choice(data_users)
        participant_2 = choice(data_users)
    return [participant_1, participant_2]


def check_winner(game):
    if game["first_votes"] > game["second_votes"]:
        return 1
    if game["first_votes"] < game["second_votes"]:
        return 2
    return 0


def check_kicked(kicked_users: list, active_users: dict):
    i = 0
    while i != len(active_users["participants"]):
        if list(active_users["participants"][i].keys())[-1] in kicked_users:
            active_users["participants"] = (
                active_users["participants"][:i]
                + active_users["participants"][i + 1 :]
            )
        else:
            i += 1
    return active_users
