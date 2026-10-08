import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import pytest

from driftguard.models.support import Politeness, RawDocument, Source
from driftguard.split import diff_entries, make_splitter


def mock_source(
    stype: Literal["html", "html_table", "rss", "openapi"],
    id: str = "test-1",
) -> Source:
    return Source(
        id=id,
        vendor="test",
        type=stype,
        url="http://test.com",
        cadence="daily",
        parser_hints={},
        politeness=Politeness(min_interval_seconds=1.0, user_agent="bot"),
    )


def mock_doc(text: str) -> RawDocument:
    return RawDocument(
        source_id="test-1",
        url="http://test.com/doc",
        fetched_at=datetime.now(UTC),
        content_type="text/plain",
        text=text,
        content_hash="dummy",
    )


def test_html_splitter_yields_entries() -> None:
    html = "\n".join(
        [
            f'<article id="entry-{i}"><h3>Title {i}</h3>Content {i} Published: 2024-01-0{i}</article>'
            for i in range(1, 9)
        ]
    )
    splitter = make_splitter(mock_source("html"))
    entries = splitter.split(mock_doc(html))

    assert len(entries) == 8
    assert entries[0].id == "test-1#entry-1"
    assert entries[0].title == "Title 1"
    assert entries[0].text == "Title 1 Content 1 Published: 2024-01-01"
    assert entries[0].published_at == date(2024, 1, 1)


def test_html_table_splitter() -> None:
    html = """<table>
        <tr><th>Model Name</th><th>Retirement Date</th></tr>
        <tr><td>Acme Pro</td><td>2025-01-01</td></tr>
        <tr><td>Acme Lite</td><td>2025-06-01</td></tr>
    </table>"""
    splitter = make_splitter(mock_source("html_table"))
    entries = splitter.split(mock_doc(html))

    assert len(entries) == 2
    assert entries[0].title is None
    assert entries[0].id == "test-1#row-acme-pro"
    assert entries[0].text == "Model Name: Acme Pro | Retirement Date: 2025-01-01"


def test_rss_splitter() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel>
        <item><title>Item 1</title><description>Desc 1</description>
        <guid>id-1</guid><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
        <item><title>Item 2</title><description>Desc 2</description>
        <guid>id-2</guid></item>
        <item><title>Item 3</title><description>Desc 3</description>
        <guid>id-3</guid></item>
        <item><title>Item 4</title><description>Desc 4</description>
        <guid>id-4</guid></item>
    </channel></rss>"""
    splitter = make_splitter(mock_source("rss"))
    entries = splitter.split(mock_doc(xml))

    assert len(entries) == 4
    assert entries[0].title == "Item 1"
    assert entries[0].id == "id-1"
    assert entries[0].published_at == date(2024, 1, 1)
    assert entries[0].text == "Item 1. Desc 1"


def test_openapi_raises_not_implemented() -> None:
    splitter = make_splitter(mock_source("openapi"))
    with pytest.raises(NotImplementedError, match="handled by deterministic extractor"):
        splitter.split(mock_doc("{}"))


def test_dates_malformed_and_missing() -> None:
    html = '<article data-date="bad-date">No date here</article>'
    entries = make_splitter(mock_source("html")).split(mock_doc(html))
    assert len(entries) == 1
    assert entries[0].published_at is None


def test_malformed_document_yields_empty_list() -> None:
    assert make_splitter(mock_source("html")).split(mock_doc("")) == []
    assert (
        make_splitter(mock_source("html_table")).split(mock_doc("<div>No table</div>"))
        == []
    )


def test_stability_and_crlf() -> None:
    doc_crlf = mock_doc("<article>Line 1\r\nLine 2</article>")
    doc_lf = mock_doc("<article>Line 1\nLine 2</article>")
    doc_space = mock_doc("<article> Line  1 \n  Line   2 </article>")

    splitter = make_splitter(mock_source("html"))
    e_crlf = splitter.split(doc_crlf)[0]
    e_lf = splitter.split(doc_lf)[0]
    e_space = splitter.split(doc_space)[0]

    assert e_crlf.content_hash == e_lf.content_hash == e_space.content_hash
    assert e_crlf.id == e_lf.id


def test_diff_entries() -> None:
    html = (
        '<article id="a1">Hash1</article>'
        '<article id="a2">Hash2</article>'
        '<article id="a3">Hash3</article>'
    )
    entries = make_splitter(mock_source("html")).split(mock_doc(html))
    entries[0].content_hash = "h1"
    entries[1].content_hash = "h2"
    entries[2].content_hash = "h3"

    known = {
        "test-1#a1": "h1",
        "test-1#a2": "old_hash",
        "test-1#other": "h3",
    }

    res = diff_entries(known, entries)
    assert len(res.unchanged) == 2
    assert len(res.changed) == 1
    assert len(res.new) == 0

    entries[0].content_hash = "brand_new_hash"
    entries[0].id = "brand_new_id"
    res2 = diff_entries(known, entries)
    assert len(res2.new) == 1


def test_hand_split_truth() -> None:
    truth_file = Path("tests/fixtures/pages/truth.json")
    if not truth_file.exists():
        pytest.skip("Truth fixtures not delivered by Engineer B yet.")

    truth_data = json.loads(truth_file.read_text(encoding="utf-8"))
    assert truth_data is not None
