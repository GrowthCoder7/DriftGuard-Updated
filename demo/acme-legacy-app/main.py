import requests


def ping_vendor():
    # Untested string literal using retired model
    requests.post("https://api.acme.com/v1/chat", json={"model": "acme-pro-2025-01"})