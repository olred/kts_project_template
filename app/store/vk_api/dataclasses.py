from dataclasses import dataclass


@dataclass
class UpdateObject:
    chat_id: int
    id: int
    body: str
    type: str


@dataclass
class UpdatePhoto(UpdateObject):
    owner_id: int
    photo_id: int
    access_key: str


@dataclass
class UpdateAction(UpdateObject):
    member_id: int


@dataclass
class Update:
    type: str
    object: UpdateObject | UpdatePhoto | UpdateAction


@dataclass
class Message:
    chat_id: int
    text: str


@dataclass
class MessageKeyboard(Message):
    keyboard: str


@dataclass
class Attachment(Message):
    attachment: list[str]


@dataclass
class MessageAttachment:
    pass
