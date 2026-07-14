"""Shared test helpers: load the hyphen-named scripts as importable modules."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent


def load_script(name: str):
    """Import scripts/<name>.py despite the hyphen in the filename."""
    module_name = name.replace("-", "_")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def bib_validator():
    return load_script("bib-validator")


@pytest.fixture(scope="session")
def journal_lookup():
    return load_script("journal-lookup")


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT
