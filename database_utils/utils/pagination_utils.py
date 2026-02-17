import math


def compute_pagination(page: int, page_size: int, total_count: int) -> tuple[int, int, int]:
    """Compute pagination values for a SQLAlchemy query.

    Args:
        page: Current page number (1-indexed).
        page_size: Number of records per page.
        total_count: Total number of records matching the query filters.

    Returns:
        tuple: (skip, total_count, total_pages)
            - skip: number of records to offset
            - total_count: same as input (passed through for convenience)
            - total_pages: total number of pages (minimum 1)
    """
    skip = (page - 1) * page_size
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
    return skip, total_count, total_pages
