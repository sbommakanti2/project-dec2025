"""CRUD helper functions the API layer can call without touching SQLAlchemy internals."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.db import models, schemas


def get_items(db: Session) -> List[models.Item]:
    """Return all items ordered newest-first."""
    return db.query(models.Item).order_by(models.Item.created_at.desc()).all()


def get_item(db: Session, item_id: int) -> Optional[models.Item]:
    """Return a single item or None if the id is unknown."""
    return db.query(models.Item).filter(models.Item.id == item_id).first()


def create_item(db: Session, item: schemas.ItemCreate) -> models.Item:
    """Insert a new record and return the hydrated ORM object."""
    db_item = models.Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_item(db: Session, db_item: models.Item, item_update: schemas.ItemUpdate) -> models.Item:
    """Mutate the provided ORM object using optional fields."""
    if item_update.name is not None:
        db_item.name = item_update.name
    if item_update.description is not None:
        db_item.description = item_update.description
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, db_item: models.Item) -> None:
    """Remove the record permanently."""
    db.delete(db_item)
    db.commit()
