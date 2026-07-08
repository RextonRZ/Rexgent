"""Every pipeline router now sits behind get_current_user (router-level
dependency). Tests exercise route logic, not auth — so a signed-in user is
faked for each test. Applied per-test (autouse) because some tests set and
then pop their own override, which would strip a module-level one."""
import uuid
from types import SimpleNamespace

import pytest

from app.main import app
from app.deps import get_current_user


@pytest.fixture(autouse=True)
def _signed_in_user():
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uuid.uuid4(), email="test@rexgent.dev"
    )
    yield
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)
