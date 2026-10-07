import json
from pathlib import Path

from driftguard.models.core import Contract, Impact, UsageRecord, Verdict


def main() -> None:
    schemas_dir = Path("schemas")
    schemas_dir.mkdir(exist_ok=True)
    models = {
        "Contract": Contract,
        "UsageRecord": UsageRecord,
        "Impact": Impact,
        "Verdict": Verdict,
    }
    for name, model in models.items():
        path = schemas_dir / f"{name.lower()}.json"
        with path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(model.model_json_schema(), f, indent=2, sort_keys=True)
            f.write("\n")


if __name__ == "__main__":
    main()
