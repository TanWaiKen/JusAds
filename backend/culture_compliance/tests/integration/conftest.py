"""Configuration for integration tests.

Registers the 'integration' mark and loads environment variables
from the .env file for integration test execution.
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env from the culture_compliance directory for integration tests
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def pytest_configure(config):
    """Register custom marks for integration tests."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring real services "
        "(AWS credentials + Qdrant connectivity)",
    )
