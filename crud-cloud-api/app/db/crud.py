from typing import List, Optional

from sqlalchemy.orm import Session

from app.db import models, schemas


def get_items(db: Session) -> List[models.Item]:
    return db.query(models.Item).order_by(models.Item.created_at.desc()).all()


def get_item(db: Session, item_id: int) -> Optional[models.Item]:
    return db.query(models.Item).filter(models.Item.id == item_id).first()


def create_item(db: Session, item: schemas.ItemCreate) -> models.Item:
    db_item = models.Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_item(db: Session, db_item: models.Item, item_update: schemas.ItemUpdate) -> models.Item:
    if item_update.name is not None:
        db_item.name = item_update.name
    if item_update.description is not None:
        db_item.description = item_update.description
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_item(db: Session, db_item: models.Item) -> None:
    db.delete(db_item)
    db.commit()
