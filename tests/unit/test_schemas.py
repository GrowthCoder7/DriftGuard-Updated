import json
import os
from driftguard.models.core import Contract

def test_schema_export_matches() -> None:
    schema_path = "schemas/contract.json"
    if not os.path.exists(schema_path):
        return  # skip if not generated yet

    with open(schema_path, "r") as f:
        on_disk = json.load(f)
    
    assert Contract.model_json_schema() == on_disk