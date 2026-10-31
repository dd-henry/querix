import logging
import time
from typing import Mapping, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import Settings, get_settings

logger = logging.getLogger(__name__)

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_HTTP_ERROR_CODES = {
    401: "auth_required",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
}


class APIError(Exception):
    """An expected API failure with a stable public error shape."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: Optional[Mapping[str, str]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def _error_response(
    status_code: int,
    code: str,
    message: str,
    headers: Optional[Mapping[str, str]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def _http_exception_details(exc: StarletteHTTPException) -> tuple[str, str]:
    default_code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
    default_message = "Request failed."
    if isinstance(exc.detail, Mapping):
        code = exc.detail.get("code", default_code)
        message = exc.detail.get("message", default_message)
        if isinstance(code, str) and isinstance(message, str):
            return code, message
    if isinstance(exc.detail, str):
        return default_code, exc.detail
    return default_code, default_message


def create_app(
    settings: Optional[Settings] = None,
    services: Optional[object] = None,
) -> FastAPI:
    """Build the API without opening external connections at import time."""

    resolved_settings = settings or get_settings()
    app = FastAPI(title="Ask SQL API")
    app.state.settings = resolved_settings
    app.state.services = services
    from api.routes.auth import router as auth_router
    from api.routes.admin import router as admin_router
    from api.routes.chat_execute import router as chat_execute_router
    from api.routes.chat_translate import router as chat_translate_router
    from api.routes.conversation_collection import router as conversation_router
    from api.routes.conversation_item import router as conversation_item_router
    from api.routes.history import router as history_router
    from api.routes.predefined import router as predefined_router

    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(admin_router)
    app.include_router(chat_execute_router)
    app.include_router(chat_translate_router)
    app.include_router(conversation_router)
    app.include_router(conversation_item_router)
    app.include_router(history_router)
    app.include_router(predefined_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def protect_origin_and_log(
        request: Request, call_next
    ) -> Response:
        started_at = time.perf_counter()
        response: Optional[Response] = None
        try:
            origin = request.headers.get("origin")
            if (
                request.method not in _SAFE_METHODS
                and origin
                and origin != resolved_settings.web_origin
            ):
                response = _error_response(
                    403,
                    "origin_not_allowed",
                    "Request origin is not allowed.",
                )
            else:
                response = await call_next(request)
            return response
        finally:
            status_code = response.status_code if response is not None else 500
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "api_request method=%s path=%s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )

    @app.exception_handler(APIError)
    async def handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,
            "validation_error",
            "Request validation failed.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code, message = _http_exception_details(exc)
        return _error_response(exc.status_code, code, message, exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error("unhandled_api_exception type=%s", type(exc).__name__)
        return _error_response(
            500,
            "internal_error",
            "Internal server error.",
        )

    return app
