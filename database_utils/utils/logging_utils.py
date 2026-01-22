"""
Centralized logging utilities for the ERP system.

This module provides structured logging capabilities with contextual information
including user ID, company ID, roles, permissions, request ID, and more.
"""

import logging
import json
import sys
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Union
from functools import wraps
from contextvars import ContextVar

from fastapi import Request
from sqlalchemy.orm import Session

# Context variables for request-scoped data
request_id_context: ContextVar[str] = ContextVar('request_id', default='')
user_id_context: ContextVar[Optional[Union[int, uuid.UUID, str]]] = ContextVar('user_id', default=None)
company_id_context: ContextVar[Optional[Union[int, uuid.UUID, str]]] = ContextVar('company_id', default=None)
user_roles_context: ContextVar[list] = ContextVar('user_roles', default=[])
user_permissions_context: ContextVar[set] = ContextVar('user_permissions', default=set())


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in JSON format for easy parsing and searching.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add context variables if available
        request_id = request_id_context.get()
        if request_id:
            log_data['request_id'] = request_id

        user_id = user_id_context.get()
        if user_id:
            log_data['user_id'] = user_id

        company_id = company_id_context.get()
        if company_id:
            log_data['company_id'] = company_id

        roles = user_roles_context.get()
        if roles:
            log_data['user_roles'] = roles

        permissions = user_permissions_context.get()
        if permissions:
            log_data['user_permissions'] = list(permissions)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }

        # Add extra fields from the log record
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        return json.dumps(log_data, default=str)


class SimpleFormatter(logging.Formatter):
    """
    Human-readable formatter for development environments.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record in a readable format."""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        # Build context string
        context_parts = []
        request_id = request_id_context.get()
        if request_id:
            context_parts.append(f"req={request_id[:8]}")

        user_id = user_id_context.get()
        if user_id:
            context_parts.append(f"user={user_id}")

        company_id = company_id_context.get()
        if company_id:
            context_parts.append(f"company={company_id}")

        context_str = f"[{' '.join(context_parts)}]" if context_parts else ""

        # Build log line
        base = f"{timestamp} [{record.levelname:8s}] {record.name} {context_str} - {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            base += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return base


def setup_logger(
    name: str,
    level: str = "INFO",
    structured: bool = False
) -> logging.Logger:
    """
    Set up a logger with the appropriate formatter.

    Args:
        name: Logger name (usually __name__ from the calling module)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: If True, use JSON formatting; otherwise use simple readable format

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper()))

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter based on environment
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = SimpleFormatter()

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Don't propagate to root logger to avoid duplicate logs
    logger.propagate = False

    return logger


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[Union[int, uuid.UUID, str]] = None,
    company_id: Optional[Union[int, uuid.UUID, str]] = None,
    user_roles: Optional[list] = None,
    user_permissions: Optional[set] = None
) -> None:
    """
    Set context variables for the current request.

    This should be called early in request processing (e.g., in middleware).

    Args:
        request_id: Unique identifier for this request
        user_id: ID of the authenticated user (int, UUID, or string)
        company_id: ID of the user's company (int, UUID, or string)
        user_roles: List of user's role names
        user_permissions: Set of user's permission strings
    """
    if request_id:
        request_id_context.set(request_id)
    if user_id is not None:
        user_id_context.set(user_id)
    if company_id is not None:
        company_id_context.set(company_id)
    if user_roles is not None:
        user_roles_context.set(user_roles)
    if user_permissions is not None:
        user_permissions_context.set(user_permissions)


def clear_request_context() -> None:
    """Clear all request context variables."""
    request_id_context.set('')
    user_id_context.set(None)
    company_id_context.set(None)
    user_roles_context.set([])
    user_permissions_context.set(set())


def get_request_context() -> Dict[str, Any]:
    """
    Get current request context as a dictionary.

    Returns:
        Dictionary containing current context values
    """
    return {
        'request_id': request_id_context.get(),
        'user_id': user_id_context.get(),
        'company_id': company_id_context.get(),
        'user_roles': user_roles_context.get(),
        'user_permissions': list(user_permissions_context.get()),
    }


def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs) -> None:
    """
    Log a message with additional context data.

    Args:
        logger: Logger instance to use
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **kwargs: Additional key-value pairs to include in the log
    """
    log_method = getattr(logger, level.lower())

    # Create a log record with extra data
    extra_data = kwargs.copy()

    # Create a custom LogRecord with extra_data attribute
    class ContextLogRecord(logging.LogRecord):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.extra_data = extra_data

    # Temporarily replace the LogRecord class
    old_factory = logging.getLogRecordFactory()
    logging.setLogRecordFactory(lambda *args, **kwargs: ContextLogRecord(*args, **kwargs))

    try:
        log_method(message)
    finally:
        logging.setLogRecordFactory(old_factory)


def log_endpoint_call(
    logger: logging.Logger,
    request: Request,
    user_id: Optional[Union[int, uuid.UUID, str]] = None,
    company_id: Optional[Union[int, uuid.UUID, str]] = None,
    roles: Optional[list] = None
) -> None:
    """
    Log an API endpoint call with full context.

    Args:
        logger: Logger instance
        request: FastAPI Request object
        user_id: Authenticated user ID (int, UUID, or string)
        company_id: User's company ID (int, UUID, or string)
        roles: User's roles
    """
    log_with_context(
        logger,
        'info',
        f"Endpoint called: {request.method} {request.url.path}",
        endpoint=request.url.path,
        method=request.method,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        user_id=user_id,
        company_id=company_id,
        roles=roles,
    )


def log_database_operation(
    logger: logging.Logger,
    operation: str,
    model: str,
    record_id: Optional[Union[int, uuid.UUID, str]] = None,
    **kwargs
) -> None:
    """
    Log a database operation.

    Args:
        logger: Logger instance
        operation: Type of operation (CREATE, READ, UPDATE, DELETE)
        model: Model/table name
        record_id: ID of the record being operated on (int, UUID, or string)
        **kwargs: Additional context
    """
    log_with_context(
        logger,
        'info',
        f"Database {operation}: {model}" + (f" (ID: {record_id})" if record_id else ""),
        operation=operation,
        model=model,
        record_id=record_id,
        **kwargs
    )


def log_performance(logger: logging.Logger, operation: str, duration_ms: float, **kwargs) -> None:
    """
    Log performance metrics for an operation.

    Args:
        logger: Logger instance
        operation: Name of the operation
        duration_ms: Duration in milliseconds
        **kwargs: Additional context
    """
    level = 'warning' if duration_ms > 1000 else 'info'
    log_with_context(
        logger,
        level,
        f"Performance: {operation} took {duration_ms:.2f}ms",
        operation=operation,
        duration_ms=duration_ms,
        **kwargs
    )


def log_business_operation(
    logger: logging.Logger,
    operation: str,
    entity_type: str,
    entity_id: Optional[Union[int, uuid.UUID, str]] = None,
    **kwargs
) -> None:
    """
    Log an important business operation.

    Args:
        logger: Logger instance
        operation: Type of business operation (e.g., 'CLIENT_CREATED', 'ORDER_PLACED')
        entity_type: Type of entity (e.g., 'Client', 'Order')
        entity_id: ID of the entity (int, UUID, or string)
        **kwargs: Additional context
    """
    log_with_context(
        logger,
        'info',
        f"Business operation: {operation} - {entity_type}" + (f" (ID: {entity_id})" if entity_id else ""),
        business_operation=operation,
        entity_type=entity_type,
        entity_id=entity_id,
        **kwargs
    )


def timed_operation(logger: logging.Logger, operation_name: str) -> Callable:
    """
    Decorator to log the execution time of a function.

    Args:
        logger: Logger instance
        operation_name: Name to use in the log message

    Returns:
        Decorator function

    Example:
        @timed_operation(logger, "fetch_clients")
        async def get_clients(db: Session):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                log_performance(logger, operation_name, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_with_context(
                    logger,
                    'error',
                    f"Operation {operation_name} failed after {duration_ms:.2f}ms: {str(e)}",
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                log_performance(logger, operation_name, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_with_context(
                    logger,
                    'error',
                    f"Operation {operation_name} failed after {duration_ms:.2f}ms: {str(e)}",
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

        # Return the appropriate wrapper based on whether the function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Pre-configured loggers for different modules
def get_app_logger(module_name: str, log_level: str = "INFO", structured: bool = False) -> logging.Logger:
    """
    Get a configured application logger.

    Args:
        module_name: Name of the module (usually __name__)
        log_level: Desired log level
        structured: Whether to use structured (JSON) logging

    Returns:
        Configured logger instance
    """
    return setup_logger(module_name, log_level, structured)
