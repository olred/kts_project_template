from sqlalchemy.orm import relationship

from app.store.database.sqlalchemy_base import db

from sqlalchemy import Column, Text, BigInteger, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB


class GameModel(db):
    __tablename__ = "game"
    id = Column(BigInteger, primary_key=True)
    chat_id = Column(
        BigInteger, ForeignKey("game_session.chat_id", ondelete="CASCADE")
    )
    users = Column(JSONB)
    state_photo = Column(Boolean)
    state_in_game = Column(Boolean)
    state_wait_votes = Column(Boolean)
    new_pair = Column(JSONB)
    first_votes = Column(BigInteger, default=0)
    second_votes = Column(BigInteger, default=0)
    state_send_photo = Column(Boolean)
    voters = Column(JSONB)
    amount_users = Column(BigInteger)
    last_winner = Column(Text)
    kicked_users = Column(JSONB)


class GameSession(db):
    __tablename__ = "game_session"
    id = Column(BigInteger, primary_key=True)
    chat_id = Column(BigInteger, unique=True)


class ParticipantsModel(db):
    __tablename__ = "participants"
    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    wins = Column(BigInteger)
    chat_id = Column(
        BigInteger, ForeignKey("game_session.chat_id", ondelete="CASCADE")
    )
    owner_id = Column(BigInteger)
    photo_id = Column(BigInteger)
    access_key = Column(Text)
