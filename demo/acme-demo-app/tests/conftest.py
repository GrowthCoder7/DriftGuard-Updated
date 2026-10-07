import sys
from pathlib import Path

# Explicitly add the acme-demo-app root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import threading
import time

import pytest
import uvicorn
from acme_stub_server.server import app


@pytest.fixture(scope="session", autouse=True)
def start_stub_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="critical")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)  # allow port to bind deterministically
    yield