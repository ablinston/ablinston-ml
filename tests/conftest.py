# Get the path of the tests directory
from pathlib import Path
import pytest

@pytest.fixture(scope = "session")
def data_path():
    return Path(__file__).parent / "data"



