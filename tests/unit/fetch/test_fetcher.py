import json
from datetime import UTC, datetime

import httpx
import pytest

from driftguard.fetch.fetcher import HttpFetcher
from driftguard.models.support import Checkpoint, Source


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


@pytest.fixture
def base_registry():
    return {
        "acme": {
            "url": "https://api.acme.com/data",
            "politeness": {"min_interval_seconds": 1.0},
            "user_agent": "TestBot",
        }
    }


def test_304_yields_zero_docs(base_registry):
    def handle(req):
        if req.headers.get("If-None-Match") == "v1":
            return httpx.Response(304)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)
    docs, _cp = f.fetch(
        Source(id="acme"), Checkpoint(cursor=json.dumps({"etag": "v1"}))
    )
    assert len(docs) == 0


def test_ETag_sent_on_second_call(base_registry):
    def handle(req):
        if req.headers.get("If-None-Match") == "v1":
            return httpx.Response(304)
        return httpx.Response(200, text="body", headers={"ETag": "v1"})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)

    docs1, cp1 = f.fetch(Source(id="acme"))
    assert len(docs1) == 1

    docs2, _cp2 = f.fetch(Source(id="acme"), cp1)
    assert len(docs2) == 0


def test_Last_Modified_sent(base_registry):
    def handle(req):
        if req.headers.get("If-Modified-Since") == "Wed, 21 Oct 2015 07:28:00 GMT":
            return httpx.Response(304)
        return httpx.Response(
            200, text="body", headers={"Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT"}
        )

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)

    _docs1, cp1 = f.fetch(Source(id="acme"))
    docs2, _cp2 = f.fetch(Source(id="acme"), cp1)
    assert len(docs2) == 0


def test_changed_body_yields_a_doc(base_registry):
    state = {"v": 1}

    def handle(req):
        if state["v"] == 1:
            state["v"] = 2
            return httpx.Response(200, text="A", headers={"ETag": "A"})
        return httpx.Response(200, text="B", headers={"ETag": "B"})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)

    _, cp = f.fetch(Source(id="acme"))
    docs, _cp2 = f.fetch(Source(id="acme"), cp)
    assert len(docs) == 1
    assert docs[0].text == "B"


def test_robots_disallow_skips(base_registry):
    def handle(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, text="body")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)

    with pytest.raises(ValueError, match="robots disallow skips"):
        f.fetch(Source(id="acme"))


def test_min_interval_enforced_with_fake_clock(base_registry):
    def handle(req):
        return httpx.Response(200, text="x")

    client = httpx.Client(transport=httpx.MockTransport(handle))

    clock = FakeClock()
    sleep = FakeSleep(clock)
    f = HttpFetcher(clock, sleep, base_registry, client=client)

    f.fetch(Source(id="acme"))
    assert sleep.slept == 0
    f.fetch(Source(id="acme"))
    assert sleep.slept >= 1.0


def test_429_Retry_After_honoured(base_registry):
    state = {"calls": 0}

    def handle(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)

        state["calls"] += 1
        if state["calls"] == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    clock = FakeClock()
    sleep = FakeSleep(clock)
    f = HttpFetcher(clock, sleep, base_registry, client=client)
    f.fetch(Source(id="acme"))
    assert sleep.slept == 2.0


def test_503_retries_then_fails_closed(base_registry):
    def handle(req):
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)
    with pytest.raises(ValueError, match="503 retries then fails closed"):
        f.fetch(Source(id="acme"))


def test_timeout_present_on_every_request(base_registry):
    def handle(req):
        assert req.extensions.get("timeout") is not None
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)
    f.fetch(Source(id="acme"))


def test_file_url_rejected_when_allow_file_False(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    reg = {
        "loc": {
            "url": p.as_uri(),
            "politeness": {"min_interval_seconds": 1},
            "user_agent": "x",
        }
    }
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), reg, allow_file=False)
    with pytest.raises(ValueError, match="file:// rejected"):
        f.fetch(Source(id="loc"))


def test_file_url_unchanged_returns_empty_list(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    reg = {
        "loc": {
            "url": p.as_uri(),
            "politeness": {"min_interval_seconds": 1},
            "user_agent": "x",
        }
    }
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), reg, allow_file=True)
    _docs1, cp = f.fetch(Source(id="loc"))
    docs2, _cp2 = f.fetch(Source(id="loc"), cp)
    assert len(docs2) == 0


def test_CRLF_and_LF_copies_of_one_fixture_give_identical_content_hash(tmp_path):
    p1 = tmp_path / "crlf.txt"
    p1.write_bytes(b"line1\r\nline2\r\n")
    p2 = tmp_path / "lf.txt"
    p2.write_bytes(b"line1\nline2\n")

    reg = {
        "s1": {
            "url": p1.as_uri(),
            "politeness": {"min_interval_seconds": 1},
            "user_agent": "x",
        },
        "s2": {
            "url": p2.as_uri(),
            "politeness": {"min_interval_seconds": 1},
            "user_agent": "x",
        },
    }
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), reg, allow_file=True)
    d1, _ = f.fetch(Source(id="s1"))
    d2, _ = f.fetch(Source(id="s2"))
    assert d1[0].content_hash == d2[0].content_hash


def test_private_host_rejected():
    reg = {
        "loc": {
            "url": "http://localhost/data",
            "politeness": {"min_interval_seconds": 1},
            "user_agent": "x",
        }
    }
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), reg, allow_local=False)
    with pytest.raises(ValueError, match="Private host rejected"):
        f.fetch(Source(id="loc"))


def test_failing_source_isolated_in_fetch_all(base_registry):
    reg = base_registry.copy()
    reg["bad"] = {
        "url": "http://bad.com",
        "politeness": {"min_interval_seconds": 1},
        "user_agent": "x",
    }

    def handle(req):
        if "acme" in str(req.url):
            return httpx.Response(200, text="ok")
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), reg, client=client)

    rep = f.fetch_all([Source(id="acme"), Source(id="bad")], {})
    assert "acme" in rep.successes
    assert "bad" in rep.failures


def test_User_Agent_matches_registry(base_registry):
    def handle(req):
        assert req.headers["User-Agent"] == "TestBot"
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handle))
    f = HttpFetcher(FakeClock(), FakeSleep(FakeClock()), base_registry, client=client)
    f.fetch(Source(id="acme"))
