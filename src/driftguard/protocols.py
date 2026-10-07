from collections.abc import Iterable
from typing import Protocol

from pydantic import BaseModel

from driftguard.models.core import (
    Contract,
    ContractCandidate,
    Impact,
    UsageRecord,
    Verdict,
)
from driftguard.models.support import (
    AliasMap,
    Budget,
    Checkpoint,
    Corpus,
    Delivery,
    Entry,
    ExtractContext,
    FixTask,
    GateDecision,
    GatePolicy,
    LLMResult,
    Patch,
    PatchResult,
    PromptRef,
    RawDocument,
    RepoSnapshot,
    ReproResult,
    Source,
    Workspace,
)


class Fetcher(Protocol):
    def fetch(
        self, source: Source, checkpoint: Checkpoint | None
    ) -> tuple[list[RawDocument], Checkpoint]: ...


class EntrySplitter(Protocol):
    def split(self, doc: RawDocument) -> list[Entry]: ...


class ContractExtractor(Protocol):
    def extract(self, entry: Entry, ctx: ExtractContext) -> list[ContractCandidate]: ...


class Validator(Protocol):
    def validate(
        self, cand: ContractCandidate, entry: Entry, corpus: Corpus
    ) -> Contract: ...


class InventoryIndexer(Protocol):
    def scan(self, snapshot: RepoSnapshot, since: str | None) -> list[UsageRecord]: ...


class Matcher(Protocol):
    def match(
        self, contract: Contract, usages: Iterable[UsageRecord], aliases: AliasMap
    ) -> list[Impact]: ...


class Simulator(Protocol):
    def reproduce(self, impact: Impact, ws: Workspace) -> ReproResult: ...


class AgentAdapter(Protocol):
    def propose_patch(self, task: FixTask, ws: Workspace) -> PatchResult: ...


class PatchGate(Protocol):
    def check(self, patch: Patch, policy: GatePolicy) -> GateDecision: ...


class Verifier(Protocol):
    def verify(self, impact: Impact, patch: Patch | None, ws: Workspace) -> Verdict: ...


class Deliverer(Protocol):
    def deliver(
        self, impact: Impact, verdict: Verdict, patch: Patch | None
    ) -> Delivery: ...


class LLMClient(Protocol):
    def complete_json(
        self, prompt: PromptRef, schema: type[BaseModel], budget: Budget
    ) -> LLMResult: ...
