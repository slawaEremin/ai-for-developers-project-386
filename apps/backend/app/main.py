import logging
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.generated.models import HealthResponse
from app.meeting_types import router

app = FastAPI(title="Календарь звонков")
app.include_router(router)


def api_error(status, code, message, field_errors=None):
    content = {"code": code, "message": message}
    if field_errors:
        content["fieldErrors"] = field_errors
    return JSONResponse(status_code=status, content=content)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exception: HTTPException):
    if request.url.path.startswith("/api/") and exception.status_code == 400:
        return api_error(400, "BAD_REQUEST", "Некорректный JSON")
    return await http_exception_handler(request, exception)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exception: RequestValidationError):
    if any(error["type"] == "json_invalid" for error in exception.errors()):
        return api_error(400, "BAD_REQUEST", "Некорректный JSON")
    errors = {}
    for error in exception.errors():
        field = str(error["loc"][-1])
        errors[field] = "Проверьте значение поля"
    return api_error(422, "VALIDATION_ERROR", "Проверьте поля формы", errors)


@app.middleware("http")
async def calendar_responses(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    try:
        if (
            request.method == "POST"
            and request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            response = api_error(
                415, "UNSUPPORTED_MEDIA_TYPE", "Требуется application/json"
            )
        else:
            response = await call_next(request)
    except psycopg.Error:
        logging.exception("Ошибка PostgreSQL")
        response = api_error(
            503, "SERVICE_UNAVAILABLE", "База данных временно недоступна"
        )
    except Exception:
        logging.exception("Неожиданная ошибка календаря")
        response = api_error(500, "INTERNAL_ERROR", "Внутренняя ошибка сервера")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


static_dir = Path(os.environ.get("STATIC_DIR", Path(__file__).parent.parent / "dist"))
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
