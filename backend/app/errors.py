import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers
        super().__init__(message)


def error_payload(request: Request, code: str, message: str, details: Any = None) -> dict:
    error = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(request, exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for error in exc.errors():
            clean = {key: value for key, value in error.items() if key != "input"}
            clean["loc"] = [str(part) for part in clean.get("loc", [])]
            if "ctx" in clean:
                clean["ctx"] = {str(key): str(value) for key, value in clean["ctx"].items()}
            details.append(clean)
        return JSONResponse(
            status_code=422,
            content=error_payload(request, "validation_error", "Request validation failed", details),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=error_payload(
                request,
                "conflict",
                "The request conflicts with existing data",
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        error_id = str(uuid.uuid4())
        # The exception is intentionally not returned to the client. The ASGI server logs it.
        return JSONResponse(
            status_code=500,
            content=error_payload(
                request,
                "internal_error",
                "An unexpected error occurred",
                {"error_id": error_id},
            ),
        )

