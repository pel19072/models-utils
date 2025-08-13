# utils/exception_handlers.py

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
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
from utils.exception_handlers import http_exception_handler, validation_exception_handler, general_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError

app = FastAPI()

# Register exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
"""