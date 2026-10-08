import fnmatch
from pathlib import Path


class CodeownersResolver:
    def __init__(self, codeowners_path: Path):
        self.rules = []
        if codeowners_path.exists():
            with open(codeowners_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        self.rules.append((parts[0], parts[1]))

    def resolve(self, path: str) -> str | None:
        owner = None
        for pattern, obj in self.rules:
            if fnmatch.fnmatch(path, pattern.lstrip("/")) or fnmatch.fnmatch(
                path, f"*{pattern}"
            ):
                owner = obj
        return owner
