import pytest
import httpx
from acme_sdk.client import AcmeClient
from app.summarizer import summarize_text

def test_stub_health():
    res = httpx.post("http://127.0.0.1:8000/v1/chat", json={"model": "acme-pro-2025-01", "messages": [], "max_tokens": 10})
    assert res.status_code == 200

def test_client_chat_success():
    client = AcmeClient()
    result = client.chat("acme-pro-2025-01", [], 10)
    assert result["choices"][0]["message"]["content"] == "Demo response"

def test_summarizer_success():
    result = summarize_text("Hello")
    assert result["choices"][0]["message"]["content"] == "Demo response"

def test_client_fails_on_bad_model():
    client = AcmeClient()
    with pytest.raises(httpx.HTTPStatusError):
        client.chat("acme-pro-2027", [], 10)

def test_client_fails_on_missing_max_tokens():
    client = AcmeClient()
    with pytest.raises(httpx.HTTPStatusError):
        client.chat("acme-pro-2025-01", [], None)