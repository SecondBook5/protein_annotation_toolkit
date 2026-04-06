"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# Configure pytest-asyncio
@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
