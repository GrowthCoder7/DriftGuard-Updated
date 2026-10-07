from .enums import ContractStatus, ImpactState

CONTRACT_TRANSITIONS: dict[ContractStatus, list[ContractStatus]] = {
    ContractStatus.NEW: [ContractStatus.EXTRACTED, ContractStatus.REJECTED],
    ContractStatus.EXTRACTED: [ContractStatus.VALIDATED, ContractStatus.NEEDS_REVIEW, ContractStatus.REJECTED],
    ContractStatus.NEEDS_REVIEW: [ContractStatus.CONFIRMED, ContractStatus.REJECTED],
    ContractStatus.VALIDATED: [ContractStatus.ACTIVE, ContractStatus.EXPIRED],
    ContractStatus.CONFIRMED: [ContractStatus.ACTIVE, ContractStatus.EXPIRED],
    ContractStatus.ACTIVE: [ContractStatus.EXPIRED],
    ContractStatus.REJECTED: [],
    ContractStatus.EXPIRED: [],
}

IMPACT_TRANSITIONS: dict[ImpactState, list[ImpactState]] = {
    ImpactState.DETECTED: [ImpactState.TRIAGED, ImpactState.CLOSED, ImpactState.SUPERSEDED],
    ImpactState.TRIAGED: [ImpactState.REPRODUCING, ImpactState.CLOSED],
    ImpactState.REPRODUCING: [ImpactState.FIXING, ImpactState.BASELINE_BROKEN, ImpactState.NOT_REPRODUCIBLE],
    ImpactState.FIXING: [ImpactState.VERIFYING, ImpactState.AGENT_FAILED],
    ImpactState.VERIFYING: [ImpactState.DELIVERED, ImpactState.FIXING],
    ImpactState.DELIVERED: [ImpactState.MERGED, ImpactState.SUPERSEDED],
    ImpactState.MERGED: [ImpactState.CLOSED],
    ImpactState.BASELINE_BROKEN: [ImpactState.CLOSED],
    ImpactState.NOT_REPRODUCIBLE: [ImpactState.CLOSED],
    ImpactState.AGENT_FAILED: [ImpactState.CLOSED],
    ImpactState.CLOSED: [],
    ImpactState.SUPERSEDED: [],
}

def can_transition(model_type: str, current: str, next_state: str) -> bool:
    if model_type.lower() == "contract":
        valid = CONTRACT_TRANSITIONS.get(ContractStatus(current), [])
        return ContractStatus(next_state) in valid
    elif model_type.lower() == "impact":
        valid = IMPACT_TRANSITIONS.get(ImpactState(current), [])
        return ImpactState(next_state) in valid
    return False