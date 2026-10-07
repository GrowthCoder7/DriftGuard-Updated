from collections.abc import Sequence
from typing import Protocol

from driftguard.models.core import Contract, ContractCandidate, UsageRecord, Verdict
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
    def fetch(self, source: Source, checkpoint: Checkpoint) -> tuple[Sequence[RawDocument], Checkpoint]: ...

class EntrySplitter(Protocol):
    def split(self, doc: RawDocument) -> Sequence[Entry]: ...

class ContractExtractor(Protocol):
    def extract(self, entry: Entry, ctx: ExtractContext) -> Sequence[ContractCandidate]: ...

class Validator(Protocol):
    def validate(self, candidate: ContractCandidate) -> Contract: ...

class InventoryIndexer(Protocol):
    def index(self, corpus: Corpus) -> None: ...

class Matcher(Protocol):
    def match(self, contract: Contract, snapshot: RepoSnapshot, aliases: AliasMap) -> Sequence[UsageRecord]: ...

class Simulator(Protocol):
    def simulate(self, contract: Contract, usages: Sequence[UsageRecord], workspace: Workspace) -> ReproResult: ...

class AgentAdapter(Protocol):
    def fix(self, task: FixTask, workspace: Workspace) -> PatchResult: ...

class PatchGate(Protocol):
    def evaluate(self, patch: Patch, policy: GatePolicy) -> GateDecision: ...

class Verifier(Protocol):
    def verify(self, patch: Patch, repro: ReproResult) -> Verdict: ...

class Deliverer(Protocol):
    def deliver(self, delivery: Delivery) -> None: ...

class LLMClient(Protocol):
    def complete(self, prompt: PromptRef, budget: Budget) -> LLMResult: ...