from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class BaseSupport(BaseModel):
    model_config = ConfigDict(extra="forbid")


SourceType = Literal["html", "html_table", "rss", "openapi"]


class Politeness(BaseSupport):
    min_interval_seconds: float
    user_agent: str


class Source(BaseSupport):
    id: str
    vendor: str
    type: SourceType
    url: str
    cadence: str
    parser_hints: dict[str, str]
    politeness: Politeness


class Checkpoint(BaseSupport):
    cursor: str


class RawDocument(BaseSupport):
    source_id: str
    url: str
    fetched_at: datetime
    content_type: str
    text: str
    content_hash: str
    etag: str | None = None
    last_modified: str | None = None


class Entry(BaseSupport):
    id: str
    source_id: str
    doc_url: str
    title: str | None = None
    published_at: date | None = None
    text: str  # text is the verbatim entry body; quotes must be substrings of it
    content_hash: str


class ExtractContext(BaseSupport):
    vendor: str
    product: str | None = None
    entry_date: date | None = None
    source_url: str
    prompt_version: str
    model: str | None = None


class Corpus(BaseSupport):
    identifiers: frozenset[str]
    corroborating_entries: list[Entry]


class RepoSnapshot(BaseSupport):
    repo: str
    path: str
    sha: str | None = None


class AliasEntry(BaseSupport):
    ontology_id: str
    sdk_symbols: list[str]
    rest_paths: list[str]
    hostnames: list[str]
    model_aliases: list[str]
    manifest_deps: list[str]


class AliasMap(BaseSupport):
    entries: list[AliasEntry]


class Workspace(BaseSupport):
    path: str


class PromptRef(BaseSupport):
    name: str
    version: str
    variables: dict[str, str]


class Budget(BaseSupport):
    max_output_tokens: int
    timeout_seconds: float


class LLMResult(BaseSupport):
    data: dict[str, Any]
    model: str
    tokens_in: int
    tokens_out: int
    cached: bool


# Phase 3 unchanged
class ReproResult(BaseSupport):
    baseline_passed: bool
    mutated_failed: bool
    evidence: str
    covering_test_found: bool
    state: str


class FixTask(BaseSupport):
    issue_id: str


class Patch(BaseSupport):
    diff: str


class PatchResult(BaseSupport):
    patch: Patch
    success: bool


class GatePolicy(BaseSupport):
    strictness: str


class GateDecision(BaseSupport):
    approved: bool


class Delivery(BaseSupport):
    destination: str
    payload: dict[str, str]
