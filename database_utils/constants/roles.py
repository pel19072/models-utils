# database_utils/constants/roles.py
"""
Role constants for role-based access control (RBAC).

These constants define the available user roles in the system
and are used for authorization checks throughout the application.
"""


class Roles:
    """
    User role constants for RBAC.

    Attributes:
        ADMIN: Administrator role with elevated privileges
        MANAGER: Manager role with most permissions except system settings
        SALES: Sales representative role with client and order permissions
        USER: Standard user role with basic permissions
        ALL: Set containing all available roles
    """

    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    SALES = "SALES"
    USER = "USER"

    ALL = {ADMIN, MANAGER, SALES, USER}
