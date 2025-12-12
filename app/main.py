import logging
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.middleware import RequestIdMiddleware
from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.request_context import get_request_id

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestIdMiddleware)
app.include_router(router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "request_id": get_request_id(),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "request_id": get_request_id(),
            }
        },
        headers=getattr(exc, "headers", None),
    )


@app.middleware("http")
async def add_correlation_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Request-ID"] = get_request_id()
    return response


@app.get("/healthz")
async def health():
    return {"status": "ok"}
