from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.db import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    player_a = Column(String)
    player_b = Column(String)
    predicted_winner = Column(String)

    win_prob_a = Column(Float)
    win_prob_b = Column(Float)
    confidence = Column(Integer)

    rating_a = Column(Float)
    rating_b = Column(Float)

    first_180_a = Column(Float)
    first_180_b = Column(Float)

    actual_winner = Column(String, nullable=True)
    actual_first_180_player = Column(String, nullable=True)

    winner_correct = Column(Integer, nullable=True)
    first_180_correct = Column(Integer, nullable=True)