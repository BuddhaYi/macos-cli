"""Pytest fixtures for macli unit tests.

`macli` is a single-file Python CLI without `.py` extension, so we load it
via importlib.util.spec_from_loader using SourceFileLoader. The loaded
module is cached at session scope so each test file pays the import cost
once.
"""

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

MACLI_PATH = Path(__file__).resolve().parent.parent / "macli"


def _load_macli():
    loader = importlib.machinery.SourceFileLoader("macli", str(MACLI_PATH))
    spec = importlib.util.spec_from_loader("macli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def macli():
    """The loaded macli module. Shared across all tests in the session."""
    return _load_macli()
