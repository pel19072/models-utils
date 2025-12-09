# utils/json_utils.py
"""
JSON serialization utilities for handling datetime and other non-JSON-serializable types.
"""
from typing import Any, Dict
from datetime import datetime, date, time, timedelta
from pydantic import BaseModel


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively serialize an object to be JSON-safe.

    Handles:
    - Pydantic models (converts to dict then serializes)
    - datetime, date, time objects (converts to ISO format strings)
    - timedelta objects (converts to total seconds)
    - dict objects (recursively serializes values)
    - list/tuple objects (recursively serializes items)
    - Other types (returns as-is)

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable version of the object
    """
    # Handle Pydantic models
    if isinstance(obj, BaseModel):
        # Use model_dump with mode='json' to get JSON-serializable output
        return obj.model_dump(mode='json')

    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()

    # Handle date objects
    if isinstance(obj, date):
        return obj.isoformat()

    # Handle time objects
    if isinstance(obj, time):
        return obj.isoformat()

    # Handle timedelta objects
    if isinstance(obj, timedelta):
        return obj.total_seconds()

    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}

    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]

    # Return other types as-is (int, str, float, bool, None, etc.)
    return obj


def pydantic_to_json_dict(model: BaseModel) -> Dict[str, Any]:
    """
    Convert a Pydantic model to a JSON-safe dictionary.

    This is a convenience wrapper around serialize_for_json specifically
    for Pydantic models. It uses Pydantic's built-in JSON serialization
    which handles datetime and other complex types correctly.

    Args:
        model: Pydantic model instance

    Returns:
        JSON-serializable dictionary
    """
    return model.model_dump(mode='json')
