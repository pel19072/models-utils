from .auth import (
    Company,
    User,
    Notification
)

from .crm import (
    Client,
    Product,
    Order,
    OrderItem,
    Invoice,
    CustomFieldDefinition,
    ClientCustomFieldValue
)

# Import all models here so Alembic can detect them
__all__ = [
    # Auth
    "Company",
    "User",
    "Notification",
    # CRM
    "Client",
    "Product",
    "Order",
    "OrderItem",
    "Invoice",
    "CustomFieldDefinition",
    "ClientCustomFieldValue"
]