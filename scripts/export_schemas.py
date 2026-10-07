import json
import os
from driftguard.models.core import Contract, UsageRecord, Impact, Verdict

def main() -> None:
    os.makedirs("schemas", exist_ok=True)
    models = {
        "Contract": Contract,
        "UsageRecord": UsageRecord,
        "Impact": Impact,
        "Verdict": Verdict
    }
    for name, model in models.items():
        path = f"schemas/{name.lower()}.json"
        with open(path, "w") as f:
            json.dump(model.model_json_schema(), f, indent=2)

if __name__ == "__main__":
    main()