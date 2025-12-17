"""Authentication helpers: hashing, faux user lookup, and JWT creation/validation."""

from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

from app.core.config import get_settings


settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _hash_password(password: str) -> str:
    """Return a deterministic SHA-256 hash for the plain password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password using constant-time comparison."""
    return secrets.compare_digest(_hash_password(plain_password), hashed_password)


# A single demo user keeps the exercise focused on API behavior rather than user storage.
fake_user_db = {
    "demo": {
        "username": "demo",
        "full_name": "Demo User",
        "hashed_password": _hash_password("password123"),
    }
}


class TokenData:
    """Pydantic-style helper for storing the username pulled from a JWT."""

    def __init__(self, username: Optional[str] = None):
        self.username = username


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Return the user dict if credentials match, else None."""
    user = fake_user_db.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Issue a signed JWT with an expiration claim."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decode the bearer token and return the corresponding fake user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc
    user = fake_user_db.get(username)
    if user is None:
        raise credentials_exception
    return user


def get_login_form(form_data: OAuth2PasswordRequestForm = Depends()) -> OAuth2PasswordRequestForm:
    """Expose FastAPI's OAuth form dependency so the login route stays tidy."""
    return form_data
