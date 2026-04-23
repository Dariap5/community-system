from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api.routes import admin_pages, analytics, funnels, payments, users


logger = logging.getLogger(__name__)

app = FastAPI(title="Community Bot API", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _normalize_http_error(detail: object) -> dict[str, object]:
    if isinstance(detail, dict):
        if "error" in detail and isinstance(detail["error"], dict):
            return detail
        if "code" in detail and "message" in detail:
            return {"error": detail}
    return {"error": {"code": "http_error", "message": str(detail)}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_normalize_http_error(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Invalid request",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": {"code": "conflict", "message": "Resource already exists"}},
    )


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Internal Server Error"}},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(funnels.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(payments.router)
app.include_router(admin_pages.router)
