from datetime import UTC, datetime

from driftguard.models.support import RawDocument


def test_RawDocument_accepts_etag_last_modified_as_optional():
    doc = RawDocument(
        source_id="acme-html",
        url="http://example.com",
        fetched_at=datetime.now(UTC),
        content_type="text/plain",
        text="data",
        content_hash="abc",
    )
    assert doc.etag is None
    assert doc.last_modified is None
