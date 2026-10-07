from typing import Sequence
from driftguard.protocols import Fetcher
from driftguard.models.support import Source, Checkpoint, RawDocument

class FakeFetcher(Fetcher):
    def fetch(self, source: Source, checkpoint: Checkpoint) -> tuple[Sequence[RawDocument], Checkpoint]:
        return [], checkpoint

def test_protocol_typing() -> None:
    f: Fetcher = FakeFetcher()
    assert f is not None