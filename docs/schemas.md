# Pydantic Schemas

## Description
Pydantic v2 request/response schemas for all models, shared between auth-erp and backend-erp to ensure consistent API contracts.

## Goal
Validate API inputs and serialize API outputs with a single shared schema definition across services.

## Schema Files (in `database_utils/schemas/`)

| File | Schemas |
|------|---------|
| `client.py` | `ClientOut`, `ClientCreate`, `ClientUpdate`, `ClientWithCustomFields` |
| `product.py` | `ProductOut`, `ProductCreate`, `ProductUpdate` |
| `order.py` | `OrderOut`, `OrderCreate`, `OrderUpdate` |
| `order_item.py` | `OrderItemOut`, `OrderItemCreate`, `OrderItemUpdate` |
| `recurring_order.py` | `RecurringOrderOut`, `RecurringOrderCreate`, `RecurringOrderUpdate` |
| `invoice.py` | `InvoiceOut`, `InvoiceCreate` |
| `user.py` | `UserOut`, `UserCreate`, `UserUpdate` |
| `company.py` | `CompanyOut`, `CompanyCreate`, `CompanyUpdate` |
| `tier.py` | `TierOut`, `TierCreate`, `TierUpdate` |
| `role.py` | `RoleOut`, `RoleCreate` |
| `permission.py` | `PermissionOut` |
| `subscription.py` | `SubscriptionOut`, `SubscriptionUpdate` |
| `payment_method.py` | `PaymentMethodOut`, `PaymentMethodCreate` |
| `billing_invoice.py` | `BillingInvoiceOut` |
| `tier_change_request.py` | `TierChangeRequestOut`, `TierChangeRequestCreate` |
| `invitation.py` | `InvitationOut`, `InvitationCreate`, `InvitationAccept` |
| `notification.py` | `NotificationOut` |
| `audit_log.py` | `AuditLogOut` |
| `custom_field.py` | `CustomFieldDefinitionOut`, `CustomFieldDefinitionCreate`, `ClientCustomFieldValueOut` |
| `task.py` | `TaskOut`, `TaskCreate`, `TaskUpdate` |
| `task_state.py` | `TaskStateOut`, `TaskStateCreate`, `TaskStateUpdate` |
| `task_template.py` | `TaskTemplateOut`, `TaskTemplateCreate` |
| `workflow.py` | `WorkflowOut`, `WorkflowCreate`, `WorkflowTriggerOut`, `WorkflowStepOut`, `WorkflowExecutionOut` |
| `pagination.py` | `PaginatedResponse[T]` — generic paginated wrapper |
| `requests.py` | `LoginRequest`, `SignupRequest`, `TokenRefreshRequest` |

## Connections to Other Components
- **auth-erp** and **backend-erp**: Import schemas directly from models-utils package
- **Auth/CRM/Workflow models**: Schemas validate against model fields

## Key Implementation Details
- All `Out` schemas use `model_config = ConfigDict(from_attributes=True)` for ORM compatibility
- Sensitive fields excluded from `Out` schemas (e.g., `password_hash`, integration `credentials`)
- `PaginatedResponse[T]`: generic wrapper with `items: list[T]`, `total`, `page`, `page_size`, `total_pages`
- Pydantic v2 validators used for field coercion and constraint checking
- UUID fields serialized as strings in JSON responses

## Environment Variables
None — schemas are pure Python/Pydantic.
