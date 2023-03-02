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
class Update:
    type: str
    object: UpdateObject | UpdatePhoto


@dataclass
class Message:
    chat_id: int
    text: str


@dataclass
class Attachment(Message):
    attachment: list[str]


@dataclass
class MessageAttachment:
    pass
