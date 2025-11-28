# utils/exception_handlers.py

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, DataError
from loguru import logger
from typing import Dict, Any, Union

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPException with custom format
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "path": request.url.path
            }
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle validation errors with more useful error messages
    """
    errors = []
    for error in exc.errors():
        # Extract location and field from error
        loc = error.get("loc", [])
        field = loc[-1] if loc else "unknown"
        
        # Extract error message
        msg = error.get("msg", "Unknown validation error")
        
        # Add to errors list
        errors.append({
            "field": field,
            "message": msg
        })
    
    logger.warning(f"Validation error: {errors}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "message": "Request validation error",
                "details": errors,
                "path": request.url.path
            }
        }
    )

async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Handle database integrity errors (foreign key violations, unique constraints)
    """
    error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)

    # Try to extract more user-friendly error messages
    if 'UNIQUE constraint failed' in error_msg or 'duplicate key value' in error_msg:
        message = "A record with this information already exists"
    elif 'FOREIGN KEY constraint failed' in error_msg or 'foreign key constraint' in error_msg.lower():
        message = "Cannot perform this operation because it would violate data relationships"
    else:
        message = "Database constraint violation"

    logger.warning(f"Integrity error: {error_msg}")

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": {
                "code": status.HTTP_409_CONFLICT,
                "message": message,
                "path": request.url.path
            }
        }
    )

async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    """
    Handle database operational errors (connection timeouts, deadlocks)
    """
    error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
    logger.error(f"Database operational error: {error_msg}")

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": status.HTTP_503_SERVICE_UNAVAILABLE,
                "message": "Database service temporarily unavailable. Please try again.",
                "path": request.url.path
            }
        }
    )

async def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
    """
    Handle database data errors (type mismatches, invalid values)
    """
    error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
    logger.warning(f"Database data error: {error_msg}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid data provided for database operation",
                "path": request.url.path
            }
        }
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle any unhandled exceptions
    """
    # Log the exception for debugging
    logger.error(f"Unhandled exception: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Internal server error",
                "path": request.url.path
            }
        }
    )

# Add this to your main.py file:
"""
from database_utils.utils.exception_handlers import (
    http_exception_handler,
    validation_exception_handler,
    integrity_error_handler,
    operational_error_handler,
    data_error_handler,
    general_exception_handler
)
from fastapi.exceptions import HTTPException, RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, DataError

app = FastAPI()

# Register exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(OperationalError, operational_error_handler)
app.add_exception_handler(DataError, data_error_handler)
app.add_exception_handler(Exception, general_exception_handler)
"""