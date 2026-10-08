#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

def check_cov(path: str) -> int:
    path_obj = Path(path)
    if not path_obj.exists():
        print(f"Skipping {path} (does not exist).")
        return 0
        
    # Check if directory only contains empty __init__.py files
    py_files = list(path_obj.rglob("*.py"))
    if not py_files or all(f.name == "__init__.py" and f.stat().st_size == 0 for f in py_files):
        print(f"Skipping {path} (empty directory or only empty __init__.py).")
        return 0

    print(f"Enforcing 85% coverage for {path}...")
    res = subprocess.run(
        ["uv", "run", "coverage", "report", f"--include={path}/*", "--fail-under=85"]
    )
    return res.returncode

def main() -> None:
    rc1 = check_cov("src/driftguard/models")
    rc2 = check_cov("src/driftguard/validate")
    if rc1 != 0 or rc2 != 0:
        print("Core coverage failed to meet the 85% threshold.")
        sys.exit(1)

if __name__ == "__main__":
    main()