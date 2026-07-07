from sqlalchemy import Column, Integer, String, Float
from app.db import Base


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, unique=True, index=True)

    elo = Column(Float)

    average = Column(Float)

    checkout = Column(Float)

    one80_rate = Column(Float)