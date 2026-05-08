"""Session-wide test configuration for zkm."""

import pytest


@pytest.fixture(autouse=True)
def _bypass_dirty_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the dirty-tree guard for all tests by default.

    CLI-touching tests should not fail because the source tree is dirty during
    development. The guard's own correctness is covered in test_devcheck.py,
    where individual tests explicitly clear this env var.
    """
    monkeypatch.setenv("ZKM_BYPASS_DIRTY_CHECK", "1")
