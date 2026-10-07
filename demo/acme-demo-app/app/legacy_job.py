from acme_sdk.client import AcmeClient

def run_untested_background_job():
    client = AcmeClient()
    client.chat(model="acme-pro-2025-01", messages=[], max_tokens=50)