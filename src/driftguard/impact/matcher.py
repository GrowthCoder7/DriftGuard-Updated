import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date

from driftguard.impact.policy import Policy
from driftguard.models.core import Contract, Impact, UsageRecord
from driftguard.models.enums import ImpactState, Severity
from driftguard.models.support import AliasMap


class ContractMatcher:
    def __init__(
        self,
        clock: Callable[[], date],
        policy: Policy,
        owner_resolver: Callable[[str, str], str | None],
    ):
        self.clock = clock
        self.policy = policy
        self.owner_resolver = owner_resolver

    def _get_severity(self, enforcement: str, days_until: int) -> str:
        if days_until < 0:
            return "critical"
        for rule in self.policy.severity_rules:
            if rule.enforcement == enforcement and days_until <= rule.days_until:
                return rule.severity
        return "low"

    def match(
        self, contract: Contract, usages: Iterable[UsageRecord], aliases: AliasMap
    ) -> list[Impact]:
        if contract.status != "ACTIVE":
            raise ValueError("Only ACTIVE contracts can be matched.")

        match_oids = {contract.surface.ref}
        target_entry = next(
            (e for e in aliases.entries if e.ontology_id == contract.surface.ref), None
        )

        if target_entry:
            """
            Alias Expansion Rule:
            Finds all ontology IDs sharing rest_paths, model_aliases, or the root SDK symbol module 
            with the targeted contract surface reference.
            """
            target_modules = {
                s.rsplit(".", 1)[0] for s in target_entry.sdk_symbols if "." in s
            }
            for entry in aliases.entries:
                if entry.ontology_id == contract.surface.ref:
                    continue
                if (
                    set(entry.rest_paths) & set(target_entry.rest_paths)
                    and target_entry.rest_paths
                    or set(entry.model_aliases) & set(target_entry.model_aliases)
                    and target_entry.model_aliases
                ):
                    match_oids.add(entry.ontology_id)
                else:
                    entry_modules = {
                        s.rsplit(".", 1)[0] for s in entry.sdk_symbols if "." in s
                    }
                    if entry_modules & target_modules and target_modules:
                        match_oids.add(entry.ontology_id)

        matched_usages = [u for u in usages if u.surface_ref in match_oids]
        if not matched_usages:
            return []

        repo_usages: defaultdict[str, list[UsageRecord]] = defaultdict(list)
        for u in matched_usages:
            repo_usages[u.repo].append(u)

        impacts = []
        today = self.clock()

        days_until = 9999
        if contract.effective.effective_at:
            days_until = (contract.effective.effective_at - today).days

        base_severity = self._get_severity(contract.effective.enforcement, days_until)
        severity_levels = ["low", "medium", "high", "critical"]

        for repo, repo_use in repo_usages.items():
            repo_sev = base_severity

            # Confidence downgrade: If all matches are sub-1.0 confidence, lower severity by 1.
            if all(u.confidence < 1.0 for u in repo_use):
                idx = severity_levels.index(repo_sev)
                if idx > 0:
                    repo_sev = severity_levels[idx - 1]

            """
            Priority Formula:
            Base priority is (100 - days_until) clamped to max 100 days away. 
            Critical severity adds +50 to the floor; High adds +30.
            Higher final float = more urgent.
            """
            priority = 100.0 - min(days_until, 100)
            if repo_sev == "critical":
                priority += 50.0
            elif repo_sev == "high":
                priority += 30.0

            owner_counts: defaultdict[str, int] = defaultdict(int)
            for u in repo_use:
                owner = self.owner_resolver(repo, u.file)
                if owner:
                    owner_counts[owner] += 1

            final_owner = None
            if owner_counts:
                # Break ties alphabetically, max count wins (min of -count)
                final_owner = min(owner_counts.items(), key=lambda x: (-x[1], x[0]))[0]

            ik = hashlib.sha256(f"{contract.id}|{repo}".encode()).hexdigest()

            impacts.append(
                Impact(
                    id=ik,
                    idempotency_key=ik,
                    contract_id=contract.id,
                    repo=repo,
                    state=ImpactState.DETECTED,
                    severity=Severity(repo_sev),
                    priority=priority,
                    owner=final_owner,
                    usages=repo_use,
                )
            )

        return impacts
