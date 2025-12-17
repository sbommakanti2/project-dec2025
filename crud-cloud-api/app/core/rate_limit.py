"""Glue code for SlowAPI so limits and error responses stay consistent."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings


settings = get_settings()
# Share a single limiter instance so every endpoint uses the same counters.
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.global_rate_limit])


def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Shape a friendly JSON payload whenever SlowAPI blocks a request."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
        headers={"Retry-After": str(exc.reset_in)},
    )


def init_rate_limiter(app: FastAPI) -> Limiter:
    """Attach the limiter + exception handler to the FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    return limiter
