# DriftGuard AI Agent Instructions

All AI implementers must strictly adhere to these rules when working in this repository:

## 1. Core Directives
- **Deterministic Tests:** Unit tests must use fixed seeds, mocks, or recorded fixtures. NO live network calls.
- **No Secrets:** Never include real API keys, proprietary source code, or internal tokens in any file.
- **Terminology:** Never describe any output, proposed patch, or extraction as "safe" or "guaranteed".
- **Frozen Contracts:** `src/driftguard/models/` and `src/driftguard/protocols.py` are strictly FROZEN. Any changes require an ADR and Architect approval.
- **Scope Limits:** Implement one component/module per PR. Limit PRs to ~400 lines of changed code.

## 2. Development Workflow
1. Branch from main using the format `a/<feature-name>`.
2. Implement code strictly according to provided specifications.
3. Open a Pull Request (PR).
4. Do NOT merge until Architect approval is granted.

## 3. Repository Layout
- `src/driftguard/`: Core package source code.
  - `models/` & `protocols.py`: Shared, frozen support types and interfaces.
  - `split/`, `impact/`, `llm/`, `extract/`, `validate/`, `store/`: Component modules.
- `tests/unit/`: Deterministic test suite mirroring the `src/` layout.
- `scripts_dev/`: Development and CI enforcement scripts.
- `docs/adr/`: Architectural Decision Records.

## 4. Verification Commands
Always verify your work with these tools before concluding a task:
- **Format:** `uv run ruff format .`
- **Lint:** `uv run ruff check --fix .`
- **Type Check:** `uv run mypy --strict src/driftguard/<component>`
- **Test:** `$env:PYTHONPATH="src"; uv run pytest`