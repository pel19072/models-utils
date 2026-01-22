# UUID Migration Plan

## Overview
This migration converts all primary keys and foreign keys from autoincrement integers to UUID-4 across the entire ERP system.

## Impact Analysis

### What Changed
1. **Models (database_utils/models/)**:
   - All `id` columns now use `Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)`
   - All foreign key columns now use `Mapped[uuid.UUID]` or `Mapped[uuid.UUID | None]`
   - Association tables updated to use Uuid type for foreign keys

2. **Schemas (database_utils/schemas/)**:
   - All ID fields changed from `int` to `UUID`
   - All ID list fields changed from `List[int]` to `List[UUID]`
   - AuditLog.resource_id changed from `Optional[int]` to `Optional[str]` (stores UUID as string)

### Breaking Changes
- **This is a DESTRUCTIVE migration**
- Existing integer IDs cannot be converted to UUIDs while preserving relationships
- All existing data in the database will be LOST unless a complex migration script is created

## Migration Strategy

### Option 1: Fresh Database (RECOMMENDED for development)
1. **Backup any critical data** (if needed)
2. Drop all existing tables
3. Run Alembic migrations to create fresh schema with UUIDs
4. Re-seed initial data

### Option 2: Data Preservation (Complex - for production)
1. Create backup of entire database
2. Create new tables with UUID columns (temporary names)
3. Copy data while generating new UUIDs for each record
4. Build mapping table (old_int_id → new_uuid_id)
5. Update all foreign keys using mapping
6. Drop old tables and rename new ones
7. Extensive testing required

## Implementation Steps (Option 1 - Fresh Database)

### 1. In models-utils:
```bash
cd /home/pel1914/ERP/models-utils

# Generate migration (requires alembic installed in venv)
alembic revision --autogenerate -m "migrate all IDs from Integer to UUID"

# Review generated migration file
# It should DROP all tables and recreate them with UUID types

# Apply migration
alembic upgrade head
```

### 2. Update version and publish:
```bash
# Update version in pyproject.toml (e.g., 0.2.0 → 0.3.0)
# Commit and push to GitHub
git add .
git commit -m "BREAKING CHANGE: Migrate all IDs from Integer to UUID-4"
git push origin main
```

### 3. Update backend services:
```bash
# In backend-erp/
cd /home/pel1914/ERP/backend-erp
pip uninstall database-utils -y
pip install git+https://github.com/pel19072/models-utils.git@main
pip freeze > requirements.txt

# In auth-erp/
cd /home/pel1914/ERP/auth-erp
pip uninstall database-utils -y
pip install git+https://github.com/pel19072/models-utils.git@main
pip freeze > requirements.txt
```

### 4. Test backend services:
- Start both services and verify no import errors
- Test CRUD operations
- Verify UUID validation in path parameters

### 5. Update frontend:
- Change all ID type definitions from `number` to `string`
- Update API calls to handle string IDs
- Remove ID columns from DataTable displays
- Test build with `npm run build`

## Post-Migration Validation

### Backend Validation:
- [ ] All models import without errors
- [ ] Alembic migration runs successfully
- [ ] CRUD operations work with UUID IDs
- [ ] Foreign key relationships maintain integrity
- [ ] JWT tokens (if they contain user IDs) still validate

### Frontend Validation:
- [ ] TypeScript compilation succeeds
- [ ] No type errors in IDE
- [ ] API calls send string IDs
- [ ] Forms accept/display UUIDs correctly
- [ ] DataTables render without ID column

## Rollback Plan
If migration fails:
1. Restore database from backup
2. Revert to previous version of models-utils
3. Re-install old dependency in both backend services
4. Revert frontend changes

## Important Notes
- UUID columns take more storage than integers (16 bytes vs 4 bytes)
- UUID generation has negligible performance impact
- UUIDs provide better security (no sequential ID enumeration)
- UUIDs enable distributed systems and prevent ID conflicts
- Frontend will need to handle UUIDs as strings (JavaScript has no native UUID type)
