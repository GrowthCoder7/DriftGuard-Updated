import httpx


class AcmeClient:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url

    def chat(self, model, messages, max_tokens):
        res = httpx.post(
            f"{self.base_url}/v1/chat",
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
        )
        res.raise_for_status()
        return res.json()