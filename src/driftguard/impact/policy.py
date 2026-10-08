from pydantic import BaseModel


class SeverityRule(BaseModel):
    enforcement: str
    days_until: int
    severity: str


class Policy(BaseModel):
    escalation_window_days: int
    repo_criticality: dict[str, str]
    severity_rules: list[SeverityRule]
