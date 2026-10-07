from enum import Enum

class ChangeType(str, Enum):
    removal = "removal"
    rename = "rename"
    deprecation = "deprecation"
    behavior_change = "behavior_change"
    default_change = "default_change"
    new_required = "new_required"
    auth_change = "auth_change"
    rate_limit = "rate_limit"
    model_retirement = "model_retirement"
    model_replacement = "model_replacement"
    additive_feature = "additive_feature"
    pricing = "pricing"
    other = "other"

class SurfaceKind(str, Enum):
    endpoint = "endpoint"
    param = "param"
    field = "field"
    header = "header"
    enum_value = "enum_value"
    model = "model"
    sdk_symbol = "sdk_symbol"
    webhook_event = "webhook_event"
    auth = "auth"
    default = "default"

class ContractStatus(str, Enum):
    NEW = "NEW"
    EXTRACTED = "EXTRACTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"

class UsageKind(str, Enum):
    import_ = "import"
    call = "call"
    config = "config"
    manifest = "manifest"
    url = "url"
    model_string = "model_string"
    runtime = "runtime"

class Detector(str, Enum):
    tree_sitter = "tree-sitter"
    rule = "rule"
    regex = "regex"
    runtime = "runtime"

class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"

class ImpactState(str, Enum):
    DETECTED = "DETECTED"
    TRIAGED = "TRIAGED"
    REPRODUCING = "REPRODUCING"
    FIXING = "FIXING"
    VERIFYING = "VERIFYING"
    DELIVERED = "DELIVERED"
    MERGED = "MERGED"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"
    BASELINE_BROKEN = "BASELINE_BROKEN"
    NOT_REPRODUCIBLE = "NOT_REPRODUCIBLE"
    AGENT_FAILED = "AGENT_FAILED"

class VerdictTier(str, Enum):
    V0 = "V0"
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    V4 = "V4"