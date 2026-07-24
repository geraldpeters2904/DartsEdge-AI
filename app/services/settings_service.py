from sqlalchemy.orm import Session

from app.models.settings import Settings


def get_settings(db: Session) -> Settings:
    settings = db.query(Settings).first()

    if settings is None:
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


def update_settings(db: Session, **kwargs) -> Settings:
    settings = get_settings(db)

    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    db.commit()
    db.refresh(settings)

    return settings