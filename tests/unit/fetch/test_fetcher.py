import json
from datetime import UTC, datetime

import httpx
import pytest

from driftguard.fetch.fetcher import HttpFetcher
from driftguard.models.support import Checkpoint, Politeness, Source


class FakeClock:
    def __init__(self):
        self.t = datetime(2024, 1, 1, tzinfo=UTC)

    def __call__(self):
        return self.t

    def advance(self, secs: float):
        self.t = datetime.fromtimestamp(self.t.timestamp() + secs, UTC)


class FakeSleep:
    def __init__(self, clock):
        self.clock = clock
        self.slept = 0.0

    def __call__(self, secs: float):
        self.slept += secs
        self.clock.advance(secs)


def make_source(id="acme", url="https://api.acme.com/data", min_int=1.0, ua="TestBot"):
    return Source(
        id=id,
        vendor="acme",
        type="html",
        url=url,
        cadence="",
        parser_hints={},
        politeness=Politeness(min_interval_seconds=min_int, user_agent=ua),
    )


def test_304_yields_zero_docs():
    def handle(req):
        if req.headers.get("If-None-Match") == "v1":
            return httpx.Response(304)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    docs, _cp = f.fetch(make_source(), Checkpoint(cursor=json.dumps({"etag": "v1"})))
    assert len(docs) == 0


def test_ETag_sent_on_second_call():
    def handle(req):
        if req.headers.get("If-None-Match") == "v1":
            return httpx.Response(304)
        return httpx.Response(200, text="body", headers={"ETag": "v1"})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    docs1, cp1 = f.fetch(make_source())
    assert len(docs1) == 1
    docs2, _cp2 = f.fetch(make_source(), cp1)
    assert len(docs2) == 0


def test_Last_Modified_sent():
    def handle(req):
        if req.headers.get("If-Modified-Since") == "Wed, 21 Oct 2015 07:28:00 GMT":
            return httpx.Response(304)
        return httpx.Response(
            200, text="body", headers={"Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT"}
        )

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    _docs1, cp1 = f.fetch(make_source())
    docs2, _cp2 = f.fetch(make_source(), cp1)
    assert len(docs2) == 0


def test_changed_body_yields_a_doc():
    state = {"v": 1}

    def handle(req):
        if state["v"] == 1:
            state["v"] = 2
            return httpx.Response(200, text="A", headers={"ETag": "A"})
        return httpx.Response(200, text="B", headers={"ETag": "B"})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    _, cp = f.fetch(make_source())
    docs, _cp2 = f.fetch(make_source(), cp)
    assert len(docs) == 1
    assert docs[0].text == "B"


def test_robots_disallow_skips():
    def handle(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, text="body")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    with pytest.raises(ValueError, match="robots disallow skips"):
        f.fetch(make_source())


def test_min_interval_enforced_with_fake_clock():
    def handle(req):
        return httpx.Response(200, text="x")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    clock, sleep = FakeClock(), FakeSleep(FakeClock())
    f = HttpFetcher(clock, sleep, client=client)
    f.fetch(make_source())
    assert sleep.slept == 0
    f.fetch(make_source())
    assert sleep.slept >= 1.0


def test_429_Retry_After_honoured():
    state = {"calls": 0}

    def handle(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        state["calls"] += 1
        if state["calls"] == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    clock, sleep = FakeClock(), FakeSleep(FakeClock())
    f = HttpFetcher(clock, sleep, client=client)
    f.fetch(make_source())
    assert sleep.slept == 2.0


def test_503_retries_then_fails_closed():
    def handle(req):
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    with pytest.raises(ValueError, match="503 retries then fails closed"):
        f.fetch(make_source())


def test_timeout_present_on_every_request():
    def handle(req):
        assert req.extensions.get("timeout") is not None
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    f.fetch(make_source())


def test_file_url_rejected_when_allow_file_False(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), allow_file=False)
    with pytest.raises(ValueError, match="file:// rejected"):
        f.fetch(make_source(url=p.as_uri()))


def test_file_url_unchanged_returns_empty_list(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), allow_file=True)
    _docs1, cp = f.fetch(make_source(url=p.as_uri()))
    docs2, _cp2 = f.fetch(make_source(url=p.as_uri()), cp)
    assert len(docs2) == 0


def test_CRLF_and_LF_copies_of_one_fixture_give_identical_content_hash(tmp_path):
    p1, p2 = tmp_path / "crlf.txt", tmp_path / "lf.txt"
    p1.write_bytes(b"line1\r\nline2\r\n")
    p2.write_bytes(b"line1\nline2\n")
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), allow_file=True)
    d1, _ = f.fetch(make_source(id="s1", url=p1.as_uri()))
    d2, _ = f.fetch(make_source(id="s2", url=p2.as_uri()))
    assert d1[0].content_hash == d2[0].content_hash


def test_private_host_rejected():
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), allow_local=False)
    with pytest.raises(ValueError, match="Private host rejected"):
        f.fetch(make_source(url="http://localhost/data"))


def test_User_Agent_matches_registry():
    def handle(req):
        assert req.headers["User-Agent"] == "TestBot"
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    f.fetch(make_source())


def test_fetch_all_file_sources(tmp_path):
    f1, f2, f3, f4 = tmp_path/"a.html", tmp_path/"b.xml", tmp_path/"c.yaml", tmp_path/"d.txt"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")
    f3.write_text("c", encoding="utf-8")
    f4.write_text("d", encoding="utf-8")
    
    sources = [
        make_source("f1", f1.as_uri()),
        make_source("f2", f2.as_uri()),
        make_source("f3", f3.as_uri()),
        make_source("f4", f4.as_uri()),
    ]
    
    # Use FakeClock instead of lambda: None
    fetcher = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), allow_file=True)
    res1 = fetcher.fetch_all(sources, {})
    assert len(res1.documents) == 4
    assert len(res1.checkpoints) == 4
    assert not res1.failures
    assert res1.documents[0].content_type == "text/html"
    assert res1.documents[1].content_type == "application/xml"
    assert res1.documents[2].content_type == "application/yaml"
    assert res1.documents[3].content_type == "text/plain"

    res2 = fetcher.fetch_all(sources, res1.checkpoints)
    assert len(res2.documents) == 0
    assert len(res2.checkpoints) == 4

def test_failing_source_isolated_in_fetch_all():
    s1 = make_source("good", "http://ok.com")
    s2 = make_source("bad", "http://bad.com")
    
    def handle(req): 
        # Explicitly fail the 'bad' source to trigger the isolation logic
        if "bad.com" in str(req.url):
            return httpx.Response(500)
        return httpx.Response(200, text="ok")
        
    client = httpx.Client(transport=httpx.MockTransport(handle))
    
    # Use FakeClock instead of lambda: None
    fetcher = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), client=client)
    res = fetcher.fetch_all([s1, s2], {})
    
    assert len(res.documents) == 1
    assert "good" in res.checkpoints
    assert "bad" in res.failures