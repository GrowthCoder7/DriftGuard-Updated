# ADR-001: Support Types and ID Formats

## Context
DriftGuard's frozen core requires strict types for the 12 Protocols defined in section 8.4, but the contract leaves their inner structures undefined. Furthermore, `Contract` entities require deterministic, stable ID generation.

## Options Considered
1. **Dictionaries everywhere:** Flexible but no type safety.
2. **Dataclasses:** Built-in but lacks strict runtime validation matching our `models/core`.
3. **Pydantic Models (`extra="forbid"`):** Strict parsing, aligns with `Contract` schemas.

## Decision
We chose **Pydantic v2 Models** for Support Types. The defined models strictly encapsulate the implied semantics (e.g., `ReproResult` tracking boolean test outcomes and string evidence). We implemented `make_contract_id` using a fast, deterministic SHA-256 hash sliced to 4 bytes across a canonical pipe-delimited string representing core identification criteria. 

## Consequences
- Requires mapping protocol responses through Pydantic.
- Guarantees zero "hidden fields" escaping validation.
- Prevents unstable IDs across process restarts (which `hash()` would cause).