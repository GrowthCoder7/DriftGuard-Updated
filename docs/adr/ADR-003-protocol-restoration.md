# ADR-003: Restoration of S0 Target Shapes

## Context
During Round 0 implementations, protocol signatures and support data structures drifted from the strict authoritative definitions specified in section 8.4 of the contract.

## Decision
We are retroactively aligning all Protocol interfaces and Pydantic Support types *exactly* to the S0 specification. All support types now carry `extra="forbid"` to prevent unauthorized schema expansion. The only ratified deviation preserved is that `Fetcher.fetch` continues to return a tuple containing the `Checkpoint`, as persistence of the cursor must be managed by the orchestrating caller, not the Fetcher.

## Consequences
- Total contract compliance restored.
- The `UsageRecord` model now strictly enforces the exact same ontology regex logic as `Surface.ref`.
- Any component injecting unauthorized metadata into supporting schemas will fail deterministically.