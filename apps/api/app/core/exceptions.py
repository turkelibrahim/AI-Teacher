from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("canli_ogretmen")

class BaseAPIException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code

class BadRequestException(BaseAPIException):
    def __init__(self, detail: str = "Bad Request"):
        super().__init__("BAD_REQUEST", detail, 400)

class UnauthorizedException(BaseAPIException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__("UNAUTHORIZED", detail, 401)

class ForbiddenException(BaseAPIException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__("FORBIDDEN", detail, 403)

class NotFoundException(BaseAPIException):
    def __init__(self, detail: str = "Not Found"):
        super().__init__("NOT_FOUND", detail, 404)

class TooManyRequestsException(BaseAPIException):
    def __init__(self, detail: str = "Too Many Requests"):
        super().__init__("TOO_MANY_REQUESTS", detail, 429)

async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    if isinstance(exc, BaseAPIException):
        logger.error(f"API Error [{correlation_id}]: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "correlation_id": correlation_id
                }
            }
        )
        
    logger.exception(f"Unhandled Exception [{correlation_id}]: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "correlation_id": correlation_id
            }
        }
    )
