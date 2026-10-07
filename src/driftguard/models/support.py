from pydantic import BaseModel, ConfigDict


class BaseSupport(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Source(BaseSupport): id: str
class Checkpoint(BaseSupport): cursor: str
class RawDocument(BaseSupport): content: str
class Entry(BaseSupport): id: str; data: dict[str, str]
class ExtractContext(BaseSupport): config: dict[str, str]
class Corpus(BaseSupport): id: str
class RepoSnapshot(BaseSupport): sha: str; tree: dict[str, str]
class AliasMap(BaseSupport): mappings: dict[str, str]
class Workspace(BaseSupport): path: str
class ReproResult(BaseSupport): 
    baseline_passed: bool
    mutated_failed: bool
    evidence: str
    covering_test_found: bool
    state: str
class FixTask(BaseSupport): issue_id: str
class Patch(BaseSupport): diff: str
class PatchResult(BaseSupport): patch: Patch; success: bool
class GatePolicy(BaseSupport): strictness: str
class GateDecision(BaseSupport): approved: bool
class Delivery(BaseSupport): destination: str; payload: dict[str, str]
class PromptRef(BaseSupport): version: str
class Budget(BaseSupport): max_tokens: int
class LLMResult(BaseSupport): output: str; tokens_used: int