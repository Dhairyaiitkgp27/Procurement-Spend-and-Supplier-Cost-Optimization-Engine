"""Shared fixtures. Runs the deterministic pipeline once per test session."""
import warnings

import pytest

warnings.filterwarnings("ignore")


@pytest.fixture(scope="session")
def cfg():
    from src.config import load_config
    return load_config()


@pytest.fixture(scope="session")
def results():
    """Full in-memory pipeline output (seed-fixed, deterministic)."""
    from src.pipeline import run_pipeline
    return run_pipeline(force_generate=True)


@pytest.fixture(scope="session")
def clean(results):
    return results["clean"]
