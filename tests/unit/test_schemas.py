import json
from pathlib import Path

from driftguard.models.core import Contract


def test_schema_export_matches() -> None:
    schema_path = Path("schemas/contract.json")
    if not schema_path.exists():
        return
    with schema_path.open("r", encoding="utf-8") as f:
        on_disk = json.loads(f.read())

    generated = json.loads(json.dumps(Contract.model_json_schema(), sort_keys=True))
    assert generated == on_disk
