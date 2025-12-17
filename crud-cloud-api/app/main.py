from datetime import timedelta
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Request, status

from app.core.config import get_settings
from app.core.rate_limit import init_rate_limiter, limiter
from app.core.security import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_login_form,
)
from app.db import crud, models, schemas
from app.db.database import Base, engine, get_db

settings = get_settings()
# SQLite tables are created on startup to avoid a separate migration step.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
init_rate_limiter(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/auth/login")
@limiter.limit(settings.login_rate_limit)
def login(request: Request, form_data=Depends(get_login_form)):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/items", response_model=schemas.ItemRead)
async def create_item(
    _request: Request,
    item: schemas.ItemCreate,
    db=Depends(get_db),
    _: dict = Depends(get_current_user),
):
    return crud.create_item(db, item)


@app.get("/items", response_model=List[schemas.ItemRead])
async def list_items(
    _request: Request,
    db=Depends(get_db),
    _: dict = Depends(get_current_user),
):
    return crud.get_items(db)


@app.get("/items/{item_id}", response_model=schemas.ItemRead)
async def read_item(
    item_id: int,
    _request: Request,
    db=Depends(get_db),
    _: dict = Depends(get_current_user),
):
    db_item = crud.get_item(db, item_id)
    if not db_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return db_item


@app.put("/items/{item_id}", response_model=schemas.ItemRead)
async def update_item(
    item_id: int,
    item_update: schemas.ItemUpdate,
    _request: Request,
    db=Depends(get_db),
    _: dict = Depends(get_current_user),
):
    db_item = crud.get_item(db, item_id)
    if not db_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return crud.update_item(db, db_item, item_update)


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    _request: Request,
    db=Depends(get_db),
    _: dict = Depends(get_current_user),
):
    db_item = crud.get_item(db, item_id)
    if not db_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    crud.delete_item(db, db_item)
    return None
