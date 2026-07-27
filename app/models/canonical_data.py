from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from app.db import Base

class RawIngestionRecord(Base):
    __tablename__ = 'raw_ingestion_records'
    id = Column(Integer, primary_key=True)
    provider = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    external_id = Column(String(160), nullable=False)
    payload_json = Column(Text, nullable=False)
    checksum = Column(String(64), nullable=False, index=True)
    retrieved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint('provider','entity_type','external_id','checksum', name='uq_raw_source_version'),)

class ProviderEntityMapping(Base):
    __tablename__ = 'provider_entity_mappings'
    id = Column(Integer, primary_key=True)
    provider = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    external_id = Column(String(160), nullable=False)
    internal_id = Column(Integer, nullable=False, index=True)
    competition_code = Column(String(40), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint('provider','entity_type','external_id', name='uq_provider_entity'),)

class DataProvenance(Base):
    __tablename__ = 'data_provenance'
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(32), nullable=False, index=True)
    internal_id = Column(Integer, nullable=False, index=True)
    field_name = Column(String(80), nullable=False)
    provider = Column(String(64), nullable=False)
    external_id = Column(String(160), nullable=True)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confidence = Column(String(16), default='reported', nullable=False)
