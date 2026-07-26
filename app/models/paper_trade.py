from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)

from app.db import Base


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)

    prediction_id = Column(
        Integer,
        ForeignKey("predictions.id"),
        nullable=False,
        index=True,
    )

    market = Column(String, nullable=False)
    selection = Column(String, nullable=False)
    bookmaker = Column(String, default="Paper Trade")

    odds = Column(Float, nullable=False)
    stake = Column(Float, nullable=False, default=1.0)

    status = Column(String, nullable=False, default="OPEN")
    profit_loss = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)