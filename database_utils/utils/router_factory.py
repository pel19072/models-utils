# utils/router_factory.py

from fastapi import APIRouter, status
from typing import Dict, Optional

def create_router(
    prefix: str,
    tag: str,
    description: Optional[str] = None,
    additional_responses: Optional[Dict[int, Dict[str, str]]] = None
) -> APIRouter:
    """
    Factory function to create consistent routers with standard responses.
    
    Args:
        prefix: URL prefix for all routes
        tag: API tag for documentation grouping
        description: Optional description for the router
        additional_responses: Additional response codes and descriptions
        
    Returns:
        Configured APIRouter with standard error responses
    """
    # Standard error responses all endpoints should handle
    standard_responses = {
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    }
    
    # Add any additional responses
    if additional_responses:
        standard_responses.update(additional_responses)
        
    return APIRouter(
        prefix=prefix,
        tags=[tag],
        responses=standard_responses,
    )