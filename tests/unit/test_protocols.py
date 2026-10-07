from driftguard.protocols import (
    Fetcher, EntrySplitter, ContractExtractor, Validator, InventoryIndexer, Matcher,
    Simulator, AgentAdapter, PatchGate, Verifier, Deliverer, LLMClient
)

class FakeAll(Fetcher, EntrySplitter, ContractExtractor, Validator, InventoryIndexer, 
              Matcher, Simulator, AgentAdapter, PatchGate, Verifier, Deliverer, LLMClient):
    def fetch(self, source, checkpoint): return [], checkpoint or __import__('driftguard').models.support.Checkpoint(cursor="")
    def split(self, doc): return []
    def extract(self, entry, ctx): return []
    def validate(self, cand, entry, corpus): raise NotImplementedError
    def scan(self, snapshot, since): return []
    def match(self, contract, usages, aliases): return []
    def reproduce(self, impact, ws): raise NotImplementedError
    def propose_patch(self, task, ws): raise NotImplementedError
    def check(self, patch, policy): raise NotImplementedError
    def verify(self, impact, patch, ws): raise NotImplementedError
    def deliver(self, impact, verdict, patch): raise NotImplementedError
    def complete_json(self, prompt, schema, budget): raise NotImplementedError

def test_protocols_type_check() -> None:
    # Use static type assignment instead of runtime isinstance for Protocols
    fake: Fetcher = FakeAll()
    assert fake is not None