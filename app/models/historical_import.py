from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from app.db import Base

class HistoricalImportBatch(Base):
    __tablename__ = 'historical_import_batches'
    id = Column(Integer, primary_key=True)
    batch_uuid = Column(String(36), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    provider = Column(String(64), nullable=False, index=True)
    competition_code = Column(String(40), nullable=False, index=True)
    status = Column(String(24), default='imported', nullable=False, index=True)
    received_rows = Column(Integer, default=0, nullable=False)
    created_matches = Column(Integer, default=0, nullable=False)
    duplicate_matches = Column(Integer, default=0, nullable=False)
    rejected_rows = Column(Integer, default=0, nullable=False)
    created_players = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    rolled_back_at = Column(DateTime, nullable=True)

class HistoricalImportItem(Base):
    __tablename__ = 'historical_import_items'
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('historical_import_batches.id'), nullable=False, index=True)
    entity_type = Column(String(24), nullable=False, index=True)
    internal_id = Column(Integer, nullable=True, index=True)
    external_id = Column(String(160), nullable=True)
    action = Column(String(24), nullable=False, index=True)
    created_by_batch = Column(Boolean, default=False, nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class PlayerAlias(Base):
    __tablename__ = 'player_aliases'
    id = Column(Integer, primary_key=True)
    provider = Column(String(64), nullable=False, index=True)
    alias = Column(String(180), nullable=False)
    alias_key = Column(String(180), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class HistoricalImportPreview(Base):
    __tablename__ = 'historical_import_previews'
    id = Column(Integer, primary_key=True)
    preview_uuid = Column(String(36), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    provider = Column(String(64), nullable=False, index=True)
    competition_code = Column(String(40), nullable=False, index=True)
    status = Column(String(24), default='pending', nullable=False, index=True)
    rows_json = Column(Text, nullable=False)
    report_json = Column(Text, nullable=False)
    batch_id = Column(Integer, ForeignKey('historical_import_batches.id'), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    committed_at = Column(DateTime, nullable=True)
