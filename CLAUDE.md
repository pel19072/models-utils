# Common Library

## Purpose
Shared utilities, types, and functions used across all backend API projects.

## Structure
```
.
├── alembic
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── alembic.ini
├── database_utils
│   ├── __init__.py
│   ├── containers
│   │   ├── __init__.py
│   │   └── jwt.py
│   ├── database.py
│   ├── migrations.py
│   ├── models
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── crm.py
│   ├── schemas
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── company.py
│   │   ├── notification.py
│   │   ├── order.py
│   │   ├── order_item.py
│   │   ├── product.py
│   │   ├── recurring_order.py
│   │   ├── requests.py
│   │   ├── tier.py
│   │   └── user.py
│   └── utils
│       ├── __init__.py
│       ├── error_handling.py
│       ├── exception_handlers.py
│       ├── jwt_utils.py
│       ├── password.py
│       └── router_factory.py
├── pyproject.toml
└── setup.cfg
```

## Usage
This library is imported by:
- backend-erp
- auth-erp

## Guidelines
- All exports must be well-typed
- Changes here affect all consuming projects
- Document breaking changes clearly

## Instructions for Claude
- This is a critical shared dependency
- Before making changes, consider impact on all consumers
- Always update version number for changes
- This is a public Python library deployed into my GitHub Account at the repository https://github.com/pel19072/models-utils. So take that into account when updating the requirements.txt of the dependant projects
- Run tests from consuming projects after changes