import pytest
import threading
import time
import uvicorn
from demo.acme_demo_app.acme_stub_server.server import app

@pytest.fixture(scope="session", autouse=True)
def start_stub_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="critical")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)  # allow port to bind deterministically
    yield