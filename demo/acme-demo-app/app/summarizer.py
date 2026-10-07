from pathlib import Path

import yaml
from acme_sdk.client import AcmeClient


def summarize_text(text: str):
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    
    client = AcmeClient(base_url=cfg["api_url"])
    return client.chat(
        model="acme-pro-2025-01",
        messages=[{"role": "user", "content": text}],
        max_tokens=100
    )