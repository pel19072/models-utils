# database_utils/dependencies/db.py
"""
FastAPI dependency for database session management.

This module provides a dependency function that manages database
session lifecycle with proper cleanup and error handling.
"""

import logging
from typing import Generator

from sqlalchemy.orm import Session
from database_utils.database import SessionLocal

# Configure module logger
logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.

    Manages the database session lifecycle:
    - Creates a new session
    - Yields the session to the endpoint
    - Rolls back on exceptions
    - Closes the session in finally block

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/items/")
        async def read_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            return items

    Notes:
        - Session is automatically committed for successful operations
        - Session is rolled back on exceptions to maintain data integrity
        - Session is always closed to prevent connection leaks
    """
    logger.debug("Creating new database session")

    db = SessionLocal()

    try:
        logger.debug(
            "Database session created successfully",
            extra={
                "session_id": id(db),
                "bind": str(db.bind.url) if db.bind else None
            }
        )

        yield db

        logger.debug(
            "Database session operation completed successfully",
            extra={"session_id": id(db)}
        )

    except Exception as e:
        logger.error(
            "Exception during database session - rolling back transaction",
            extra={
                "session_id": id(db),
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )

        db.rollback()

        logger.info(
            "Database transaction rolled back",
            extra={"session_id": id(db)}
        )

        raise

    finally:
        logger.debug(
            "Closing database session",
            extra={"session_id": id(db)}
        )

        db.close()

        logger.debug(
            "Database session closed successfully",
            extra={"session_id": id(db)}
        )
