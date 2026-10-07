import json
from pathlib import Path

def run():
    repo_root = Path(__file__).parent.parent
    jsonl_path = repo_root / "gold/g0_seed.jsonl"
    fixtures = [
        (repo_root / "tests/fixtures/acme/changelog.html").read_text(),
        (repo_root / "tests/fixtures/acme/deprecations.html").read_text()
    ]
    
    with open(jsonl_path) as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            if data.get("expected") == "no_contract":
                continue
            
            quote = data["evidence"]
            found = any(quote in fix for fix in fixtures)
            if not found:
                raise ValueError(f"Line {i+1}: Quote '{quote}' not found in fixtures.")
    print("All quotes strictly verified against raw fixture text.")

if __name__ == "__main__":
    run()