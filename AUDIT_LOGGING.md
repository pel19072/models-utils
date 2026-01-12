# Audit Logging Implementation Guide

## Overview

This document describes the comprehensive audit logging system implemented in version 0.7.0 of the `database-utils` library. The audit logging system tracks all CRUD operations across the ERP system, capturing user context, IP addresses, and detailed before/after states for updates.

## Features

- **Automatic tracking** of CREATE, UPDATE, and DELETE operations
- **User context capture** from JWT tokens
- **IP address tracking** from HTTP requests (supports proxied requests)
- **Before/after state tracking** for UPDATE operations
- **Resource data preservation** for DELETE operations
- **Flexible custom operation logging** for non-CRUD actions
- **Easy integration** with existing FastAPI endpoints via dependency injection

## Database Schema

The audit logs are stored in the `audit_log` table with the following structure:

```python
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    action = Column(String, nullable=False)  # e.g., "client.create"
    resource_type = Column(String, nullable=False)  # e.g., "client"
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Before/after states, context
    ip_address = Column(String, nullable=True)
```

## Core Components

### 1. Audit Utilities (`database_utils/utils/audit_utils.py`)

The audit utilities module provides convenience functions for logging different types of operations:

#### `log_create_operation()`
Logs the creation of a new resource.

```python
log_create_operation(
    db=db,
    user_id=user.id,
    resource_type="client",
    resource_id=new_client.id,
    resource_data=client_data,
    ip_address=ip_address
)
```

#### `log_update_operation()`
Logs updates to existing resources with before/after states.

```python
log_update_operation(
    db=db,
    user_id=user.id,
    resource_type="client",
    resource_id=client.id,
    before_data=before_state,
    after_data=after_state,
    ip_address=ip_address
)
```

#### `log_delete_operation()`
Logs deletion of resources, preserving the data before deletion.

```python
log_delete_operation(
    db=db,
    user_id=user.id,
    resource_type="client",
    resource_id=client_id,
    resource_data=client_data,
    ip_address=ip_address
)
```

#### `log_custom_operation()`
Logs custom operations that don't fit the standard CRUD pattern.

```python
log_custom_operation(
    db=db,
    user_id=user.id,
    action="user.activate",
    resource_type="user",
    resource_id=user_id,
    details={"previous_status": "inactive"},
    ip_address=ip_address
)
```

### 2. Audit Context Dependencies (`database_utils/dependencies/audit.py`)

#### `get_client_ip(request: Request)`
Extracts the client IP address from the request, handling proxied requests.

Checks headers in this order:
1. `X-Forwarded-For` (most common for proxied requests)
2. `X-Real-IP` (alternative proxy header)
3. `request.client.host` (direct connection)

#### `AuditContext`
Container class that holds audit-related information:
- `user_id`: ID of the authenticated user
- `ip_address`: Client IP address
- `user`: Full user object (optional)

#### `get_audit_context()`
Dependency for authenticated endpoints that captures both user and IP address.

```python
@router.post("/clients")
async def create_client(
    client_in: ClientCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("clients.create", get_db))
):
    ip_address = get_client_ip(request)
    # ... create client ...
    log_create_operation(db, user.id, "client", client.id, client_data, ip_address)
```

#### `get_audit_context_optional()`
Dependency for endpoints that may or may not require authentication.

## Integration Guide

### Step 1: Import Required Modules

```python
from fastapi import Request
from database_utils.dependencies.audit import get_client_ip
from database_utils.utils.audit_utils import (
    log_create_operation,
    log_update_operation,
    log_delete_operation,
    log_custom_operation
)
```

### Step 2: Add Request Parameter to Endpoint

Add `request: Request` to capture the HTTP request context:

```python
async def create_client(
    client_in: ClientBase,
    request: Request,  # Add this
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("clients.create", get_db))
):
```

### Step 3: Capture IP Address

At the beginning of your endpoint:

```python
ip_address = get_client_ip(request)
```

### Step 4: Log the Operation

#### For CREATE operations:

```python
# After creating and committing the resource
log_create_operation(
    db=db,
    user_id=user.id,
    resource_type="client",
    resource_id=new_client.id,
    resource_data=client_in.dict(),  # or the SQLAlchemy model
    ip_address=ip_address
)
```

#### For UPDATE operations:

```python
# BEFORE making changes
before_data = {c.name: getattr(resource, c.name) for c in resource.__table__.columns}

# ... make updates ...
# ... commit changes ...

# AFTER committing changes
after_data = {c.name: getattr(resource, c.name) for c in resource.__table__.columns}

log_update_operation(
    db=db,
    user_id=user.id,
    resource_type="client",
    resource_id=client.id,
    before_data=before_data,
    after_data=after_data,
    ip_address=ip_address
)
```

#### For DELETE operations:

```python
# BEFORE deleting (capture the data first)
resource_data = {c.name: getattr(resource, c.name) for c in resource.__table__.columns}

log_delete_operation(
    db=db,
    user_id=user.id,
    resource_type="client",
    resource_id=resource_id,
    resource_data=resource_data,
    ip_address=ip_address
)

# Then delete
db.delete(resource)
db.commit()
```

## Resource Naming Conventions

Use consistent, lowercase resource type names:

| Model | Resource Type |
|-------|---------------|
| Client | `"client"` |
| Order | `"order"` |
| Product | `"product"` |
| RecurringOrder | `"recurring_order"` |
| User | `"user"` |
| Company | `"company"` |
| Tier | `"tier"` |
| UserInvitation | `"user_invitation"` |

## Action Naming Conventions

Actions follow the pattern `{resource_type}.{operation}`:

- **CREATE**: `"client.create"`, `"user.create"`
- **UPDATE**: `"client.update"`, `"user.update"`
- **DELETE**: `"client.delete"`, `"user.delete"`
- **CUSTOM**: `"user.activate"`, `"subscription.cancel"`, `"invitation.accept"`

## Example Implementations

### Complete CREATE Example

```python
@router.post("/products", response_model=ProductOut)
@handle_exceptions
async def create_product(
    product_in: ProductBase,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.create", get_db))
):
    ip_address = get_client_ip(request)

    product = Product(**product_in.dict(), company_id=user.company_id)
    db.add(product)
    db.commit()
    db.refresh(product)

    log_create_operation(
        db=db,
        user_id=user.id,
        resource_type="product",
        resource_id=product.id,
        resource_data=product_in.dict(),
        ip_address=ip_address
    )

    return product
```

### Complete UPDATE Example

```python
@router.patch("/products/{id}", response_model=ProductOut)
@handle_exceptions
async def update_product(
    id: int,
    product_in: ProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.update", get_db))
):
    ip_address = get_client_ip(request)

    product = db.query(Product).filter_by(id=id, company_id=user.company_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Capture before state
    before_data = {c.name: getattr(product, c.name) for c in product.__table__.columns}

    # Apply updates
    for field, value in product_in.dict(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    # Capture after state
    after_data = {c.name: getattr(product, c.name) for c in product.__table__.columns}

    # Log the update
    log_update_operation(
        db=db,
        user_id=user.id,
        resource_type="product",
        resource_id=product.id,
        before_data=before_data,
        after_data=after_data,
        ip_address=ip_address
    )

    return product
```

### Complete DELETE Example

```python
@router.delete("/products/{id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_exceptions
async def delete_product(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products.delete", get_db))
):
    ip_address = get_client_ip(request)

    product = db.query(Product).filter_by(id=id, company_id=user.company_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Capture data BEFORE deletion
    product_data = {c.name: getattr(product, c.name) for c in product.__table__.columns}

    # Log deletion BEFORE actually deleting
    log_delete_operation(
        db=db,
        user_id=user.id,
        resource_type="product",
        resource_id=id,
        resource_data=product_data,
        ip_address=ip_address
    )

    # Now delete
    db.delete(product)
    db.commit()

    return None
```

### Custom Operation Example

```python
@router.patch("/users/{id}/activate", response_model=UserOut)
@handle_exceptions
async def activate_user(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_admin_user)
):
    ip_address = get_client_ip(request)

    target_user = db.query(User).filter_by(id=id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Custom operation logging
    log_custom_operation(
        db=db,
        user_id=user.id,
        action="user.activate",
        resource_type="user",
        resource_id=target_user.id,
        details={
            "previous_status": "inactive",
            "activated_by": user.email
        },
        ip_address=ip_address
    )

    target_user.active = True
    db.commit()
    db.refresh(target_user)

    return target_user
```

## Querying Audit Logs

### Get all audit logs for a specific resource

```python
logs = db.query(AuditLog).filter(
    AuditLog.resource_type == "client",
    AuditLog.resource_id == client_id
).order_by(AuditLog.created_at.desc()).all()
```

### Get all actions by a specific user

```python
logs = db.query(AuditLog).filter(
    AuditLog.user_id == user_id
).order_by(AuditLog.created_at.desc()).all()
```

### Get all deletions

```python
deletions = db.query(AuditLog).filter(
    AuditLog.action.like("%.delete")
).order_by(AuditLog.created_at.desc()).all()
```

### Get audit trail for compliance reporting

```python
from datetime import datetime, timedelta

thirty_days_ago = datetime.utcnow() - timedelta(days=30)
logs = db.query(AuditLog).filter(
    AuditLog.created_at >= thirty_days_ago,
    AuditLog.resource_type.in_(["user", "company", "tier"])
).order_by(AuditLog.created_at.desc()).all()
```

## Performance Considerations

1. **Async Operations**: The audit logging functions are synchronous and commit immediately. This ensures audit logs are persisted even if the main transaction fails.

2. **JSON Serialization**: The `details` field uses `serialize_for_json()` utility to handle Pydantic models, datetime objects, and other non-JSON-serializable types automatically.

3. **Indexing**: Consider adding database indexes on frequently queried columns:
   - `created_at` for time-based queries
   - `user_id` for user activity tracking
   - `resource_type` and `resource_id` for resource history

4. **Data Volume**: Audit logs grow over time. Implement a retention policy and archival strategy based on compliance requirements.

## Security Considerations

1. **Sensitive Data**: Be careful not to log sensitive information like passwords or tokens in the `details` field.

2. **PII Compliance**: Ensure audit logging complies with GDPR, CCPA, and other privacy regulations. Include audit log data in data export and deletion requests.

3. **Access Control**: Restrict access to audit logs to administrators and authorized personnel only.

4. **Tampering Protection**: Audit logs should never be updated or deleted through normal application logic. Implement separate archival processes with proper authorization.

## Migration Notes

The `audit_log` table already exists in the database schema (defined in `database_utils/models/auth.py`). No new migrations are required for the basic implementation.

## Changelog

### Version 0.7.0
- Added comprehensive audit logging utilities
- Added audit context dependencies for capturing user and IP address
- Added convenience functions for CREATE, UPDATE, DELETE, and custom operations
- Updated audit_utils.py from async to sync to match the codebase architecture
- Added IP address extraction with proxy support
- Added comprehensive documentation

## Support

For questions or issues related to audit logging, please refer to:
- This documentation file
- The source code in `database_utils/utils/audit_utils.py`
- The dependency module in `database_utils/dependencies/audit.py`
- Example implementations in `backend-erp/routers/` and `auth-erp/routers/`
