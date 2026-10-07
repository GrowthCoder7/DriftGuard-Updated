from demo.acme_demo_app.acme_sdk.client import AcmeClient

def run_untested_background_job():
    # Test-free module using the legacy parameters
    client = AcmeClient()
    client.chat(model="acme-pro-2025-01", messages=[], max_tokens=50)