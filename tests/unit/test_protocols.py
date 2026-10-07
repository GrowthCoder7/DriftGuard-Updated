from collections.abc import Sequence

from driftguard.models.support import Checkpoint, RawDocument, Source
from driftguard.protocols import Fetcher


class FakeFetcher(Fetcher):
    def fetch(
        self, source: Source, checkpoint: Checkpoint
    ) -> tuple[Sequence[RawDocument], Checkpoint]:
        return [], checkpoint


def test_protocol_typing() -> None:
    f: Fetcher = FakeFetcher()
    assert f is not None
