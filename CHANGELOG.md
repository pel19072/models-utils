# Changelog

All notable changes to the `database-utils` library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-01-12

### Added
- **Comprehensive Audit Logging System**
  - New audit logging utilities in `database_utils/utils/audit_utils.py`
    - `log_create_operation()` - Log resource creation with full details
    - `log_update_operation()` - Log updates with before/after states
    - `log_delete_operation()` - Log deletions with preserved resource data
    - `log_custom_operation()` - Log custom actions not fitting CRUD pattern
  - New audit context dependencies in `database_utils/dependencies/audit.py`
    - `AuditContext` class for holding audit information
    - `get_client_ip()` function with proxy support (X-Forwarded-For, X-Real-IP)
    - `get_audit_context()` dependency for authenticated endpoints
    - `get_audit_context_optional()` dependency for optional authentication
  - Comprehensive documentation in `AUDIT_LOGGING.md` with integration guide and examples

### Changed
- Updated `audit_utils.py` from async to sync operations to match codebase architecture
- Enhanced `dependencies/__init__.py` to export new audit context dependencies
- Updated package description to highlight audit logging capabilities

### Fixed
- Improved JSON serialization in audit utilities to handle Pydantic models, datetime objects, and SQLAlchemy models

## [0.6.1] - 2025-XX-XX

### Previous release
- (Previous changes not documented here)

---

## Migration Guide to 0.7.0

### For Existing Projects

1. **Update the dependency** in your `requirements.txt`:
   ```
   git+https://github.com/pel19072/models-utils.git@main
   ```

2. **Import the new utilities** where needed:
   ```python
   from database_utils.dependencies.audit import get_client_ip
   from database_utils.utils.audit_utils import (
       log_create_operation,
       log_update_operation,
       log_delete_operation
   )
   ```

3. **Add audit logging to your endpoints**:
   - Add `request: Request` parameter to capture HTTP context
   - Capture IP address: `ip_address = get_client_ip(request)`
   - Add appropriate logging calls after CRUD operations

4. **No database migrations required** - The `audit_log` table already exists in the schema.

### Breaking Changes

None. This release is fully backward compatible.

### New Features Available

- Track all CRUD operations across your application
- Capture user context automatically from JWT tokens
- Record IP addresses with proxy support
- Store before/after states for updates
- Preserve deleted resource data for compliance

See `AUDIT_LOGGING.md` for detailed implementation guide and examples.
