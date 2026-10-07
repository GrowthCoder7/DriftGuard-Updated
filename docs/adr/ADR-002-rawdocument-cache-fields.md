# ADR-002: Caching Fields on RawDocument

## Context
Our A1 Fetcher implementation needs to support Conditional GETs to respect politeness constraints, save bandwidth, and adhere to HTTP standards (ETag and Last-Modified). The `Fetcher` protocol specifies returning a `Checkpoint` cursor to pass state between runs.

## Decision
We add optional `etag` and `last_modified` fields to `RawDocument` in `src/driftguard/models/support.py` alongside the newly specified document properties (`url`, `text`, etc.). 

## Consequences
- The Fetcher can read these HTTP headers directly off fetched documents.
- These fields are serialized into the `Checkpoint.cursor` JSON string, allowing subsequent `fetch()` calls to inject `If-None-Match` and `If-Modified-Since` headers.
- If a server responds with `304 Not Modified`, we yield `[]` and preserve the cursor without re-downloading bytes.