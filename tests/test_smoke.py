"""Smoke tests: the package and its models import without error."""


def test_package_imports():
    import database_utils  # noqa: F401


def test_models_import():
    from database_utils.models import auth, crm  # noqa: F401

    assert hasattr(auth, "User")
    assert hasattr(crm, "Client")
