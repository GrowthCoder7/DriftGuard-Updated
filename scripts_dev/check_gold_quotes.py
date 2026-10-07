import json
from pathlib import Path

from driftguard.models.core import Contract


def run():
    repo_root = Path(__file__).parent.parent
    jsonl_path = repo_root / "gold/g0_seed.jsonl"
    fixtures = [
        (repo_root / "tests/fixtures/acme/changelog.html").read_text(),
        (repo_root / "tests/fixtures/acme/deprecations.html").read_text(),
    ]

    valid_count = 0
    with open(jsonl_path) as f:
        for i, line in enumerate(f):
            data = json.loads(line)

            if "expected" in data:
                continue

            for ev in data.get("evidence", []):
                quote = ev["quote"]
                found = any(quote in fix for fix in fixtures)
                if not found:
                    raise ValueError(
                        f"Line {i + 1}: Quote '{quote}' not found in fixtures."
                    )

            data.pop("label_notes", None)

            Contract(**data)
            valid_count += 1

    print("All quotes strictly verified against raw fixture text.")
    print(f"{valid_count} gold lines successfully validated against Contract schema.")


if __name__ == "__main__":
    run()
