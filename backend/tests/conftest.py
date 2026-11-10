import pytest
from app.dependencies.auth import require_current_user, SYSTEM_DEFAULT_USER
from app.main import app


@pytest.fixture(autouse=True)
def default_auth_for_legacy_tests(request):
    """
    For tests that test authentication and authorization explicitly (test_auth_isolation.py),
    do NOT override require_current_user so real authentication, token hashing, and 401 checks execute.
    For legacy test suites that were written prior to strict multi-user authentication enforcement,
    override require_current_user to authenticate as SYSTEM_DEFAULT_USER.
    """
    filename = getattr(request.node.fspath, "basename", "") or getattr(request.node, "name", "")
    if (
        "test_auth_isolation" in str(filename)
        or "test_production_duplicate_detection" in str(filename)
        or "test_content_safety" in str(filename)
    ):
        yield
    else:
        app.dependency_overrides[require_current_user] = lambda: SYSTEM_DEFAULT_USER
        try:
            yield
        finally:
            app.dependency_overrides.pop(require_current_user, None)

