import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    ChangeType,
    ContractStatus,
    Detector,
    ImpactState,
    Severity,
    SurfaceKind,
    UsageKind,
    VerdictTier,
)


class Surface(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: SurfaceKind
    ref: str = Field(pattern=r"^[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+$")
    method: str | None = None
    path: str | None = None
    language: str | None = None

class Effective(BaseModel):
    model_config = ConfigDict(extra="forbid")
    announced_at: date | None = None
    effective_at: date | None = None
    enforcement: Literal["hard", "soft", "unknown"]

class RequiredAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["none", "rename", "remove", "migrate", "upgrade_sdk", "change_config", "review"]
    text: str

class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote: str = Field(max_length=500)
    source_url: str
    entry_id: str

class Checks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_valid: bool
    quote_verbatim: bool
    identifier_grounded: bool
    date_valid: bool
    corroborated: bool
    self_consistent: bool

class Confidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: Literal["A", "B", "C", "D"]
    checks: Checks
    extractor: Literal["deterministic", "llm"]
    model: str | None = None
    prompt_version: str | None = None

class ContractCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    vendor: str
    product: str
    change_type: ChangeType
    surface: Surface
    before: dict[str, str] | None = None
    after: dict[str, str] | None = None
    effective: Effective
    scope_conditions: list[str]
    required_action: RequiredAction
    evidence: list[Evidence] = Field(min_length=1)

class Contract(ContractCandidate):
    model_config = ConfigDict(extra="forbid")
    id: str
    confidence: Confidence
    status: ContractStatus

def make_contract_id(vendor: str, product: str, surface_ref: str, change_type: str, effective_at: str | None, entry_id: str) -> str:
    eff = effective_at if effective_at else "undated"
    canon = f"{vendor}|{product}|{surface_ref}|{change_type}|{eff}|{entry_id}"
    h = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:4]
    try:
        kind = surface_ref.split(":")[2]
    except IndexError:
        kind = "unknown"
    return f"{vendor}-{product}-{kind}-{change_type}-{eff}-{h}"

class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str
    commit_sha: str
    file: str
    line: int
    symbol: str
    vendor: str
    surface_ref: str
    kind: UsageKind
    confidence: float = Field(ge=0.0, le=1.0)
    detector: Detector

class Impact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    contract_id: str
    repo: str
    usages: list[UsageRecord]
    severity: Severity
    priority: float
    owner: str | None = None
    deadline: date | None = None
    state: ImpactState
    idempotency_key: str

class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: VerdictTier
    evidence_refs: dict[Literal["baseline", "mutated", "post_fix", "probe"], str]
    limitations: str
    generated_at: datetime

    @model_validator(mode="after")
    def validate_limitations(self) -> "Verdict":
        if self.tier in (VerdictTier.V1, VerdictTier.V2, VerdictTier.V3) and (not self.limitations or self.limitations.strip() == ""):
            raise ValueError(f"Limitations required for tier {self.tier}")
        return self