# ADR-004: Entry Splitter Component (C3) Implementation

## Context
We need to parse raw HTML, RSS, and OpenAPI documents fetched by the system into discrete, normalized `Entry` objects for extraction. The splitting logic must be entirely deterministic, stable across whitespace/line-ending differences, and computationally efficient since it will run continuously over polling cycles.

## Decision
1. **HTML Parsing:** We will use `selectolax` (C-bindings for Modest engine) rather than BeautifulSoup to guarantee maximal throughput with minimal memory footprint.
2. **RSS Parsing:** We will use the standard `feedparser` library, which properly handles fragmented and legacy RSS/Atom schemas out-of-the-box.
3. **Normalization:** All text runs through Unicode NFC normalization and aggressive whitespace collapsing before hash generation.
4. **Change Detection:** "Unseen hash" is treated as the exclusive signal for a novel entry. If a source mutates DOM IDs but delivers the exact same textual payload, it will be classified as `unchanged` to prevent redundant LLM extraction.

## Consequences
- Fast, deterministic pipeline with low impedance.
- Requires `selectolax` and `feedparser` as core dependencies.
- Extractor component is protected from redundant calls by the strict `diff_entries` hash boundary.