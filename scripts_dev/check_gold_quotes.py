import json
import re
from pathlib import Path
from driftguard.models.core import Contract

def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def run():
    repo_root = Path(__file__).parent.parent
    jsonl_path = repo_root / "gold/g0_seed.jsonl"
    fixtures = [
        (repo_root / "tests/fixtures/acme/changelog.html").read_text(encoding="utf-8"),
        (repo_root / "tests/fixtures/acme/deprecations.html").read_text(encoding="utf-8"),
    ]
    norm_fixtures = [normalize(f) for f in fixtures]

    valid_count = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            if "expected" in data:
                continue
            
            for ev in data.get("evidence", []):
                quote = normalize(ev["quote"])
                found = any(quote in fix for fix in norm_fixtures)
                if not found:
                    raise ValueError(f"Line {i+1}: Quote '{quote}' not found in normalized fixtures.")
            
            data.pop("label_notes", None)
            Contract(**data)
            valid_count += 1
            
    print(f"Success: {valid_count} gold lines strictly validated against the Contract schema.")

if __name__ == "__main__":
    run()