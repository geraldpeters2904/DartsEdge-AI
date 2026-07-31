import hashlib, json
from sqlalchemy.orm import Session
from app.models.canonical_data import RawIngestionRecord, ProviderEntityMapping, DataProvenance

SUPPORTED_COMPETITIONS = ['MODUS','PDC','WDF','ADC','CDC','OTHER']
SUPPORTED_ENTITIES = ['player','competition','fixture','result','match_stats','odds']

def store_raw(db: Session, provider: str, entity_type: str, external_id: str, payload: dict):
    if entity_type not in SUPPORTED_ENTITIES:
        raise ValueError('Unsupported entity type')
    canonical = json.dumps(payload, sort_keys=True, separators=(',',':'))
    checksum = hashlib.sha256(canonical.encode()).hexdigest()
    existing = db.query(RawIngestionRecord).filter_by(provider=provider, entity_type=entity_type, external_id=external_id, checksum=checksum).first()
    if existing:
        return existing, False
    row = RawIngestionRecord(provider=provider, entity_type=entity_type, external_id=external_id, payload_json=canonical, checksum=checksum)
    db.add(row); db.commit(); db.refresh(row)
    return row, True

def map_entity(db: Session, provider: str, entity_type: str, external_id: str, internal_id: int, competition_code=None):
    row = db.query(ProviderEntityMapping).filter_by(provider=provider, entity_type=entity_type, external_id=external_id).first()
    if row:
        row.internal_id = internal_id
        if competition_code: row.competition_code = competition_code
    else:
        row = ProviderEntityMapping(provider=provider, entity_type=entity_type, external_id=external_id, internal_id=internal_id, competition_code=competition_code)
        db.add(row)
    db.commit(); db.refresh(row); return row

def record_provenance(db: Session, entity_type: str, internal_id: int, field_name: str, provider: str, external_id=None, confidence='reported'):
    row = DataProvenance(entity_type=entity_type, internal_id=internal_id, field_name=field_name, provider=provider, external_id=external_id, confidence=confidence)
    db.add(row); db.commit(); db.refresh(row); return row

def summary(db: Session):
    return {
      'raw_records': db.query(RawIngestionRecord).count(),
      'mappings': db.query(ProviderEntityMapping).count(),
      'provenance_records': db.query(DataProvenance).count(),
      'supported_competitions': SUPPORTED_COMPETITIONS,
      'supported_entities': SUPPORTED_ENTITIES,
      'architecture': 'provider-independent'
    }
