from app.store.database.sqlalchemy_base import db

from sqlalchemy import (
    Column,
    Text,
    BigInteger,
)


class ParticipantsModel(db):
    __tablename__ = "participants"
    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    wins = Column(BigInteger)
    chat_id = Column(BigInteger, nullable=False)
    owner_id = Column(BigInteger)
    photo_id = Column(BigInteger)
    access_key = Column(Text)
