"""The web server survives bad input, says nothing about its own errors, and sends safe headers."""
import json
import socket
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tutor import routes
from tutor.pack import load_pack
from tutor.server import App, MIN_TOKEN, make_handler, same_secret, serve
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
TOKEN = "a-long-enough-token-for-the-tests"


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("TUTOR_WA_TOKEN", "wa-token-123")
    monkeypatch.setenv("WHATSAPP_TO", "+447700900123")
    app = App(load_pack(PACKS, "security-plus-sy0-701", tmp_path), Store(tmp_path / "t.db"), tmp_path, token=TOKEN)
    handler = make_handler(app)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], handler
    srv.shutdown()


def raw(port, request: bytes, wait=3.0) -> bytes:
    s = socket.create_connection(("127.0.0.1", port), timeout=wait)
    s.sendall(request)
    data = b""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        data += b"<<open>>"
    s.close()
    return data


def status(resp: bytes) -> str:
    return resp.split(b"\r\n")[0].decode(errors="replace") if resp else "<closed>"


def post(port, path, body=b"{}", length=None, auth=TOKEN):
    length = len(body) if length is None else length
    return raw(port, (f"POST {path} HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer {auth}\r\nContent-Length: {length}\r\n"
                      "Connection: close\r\n\r\n").encode() + body)


def test_a_non_ascii_token_is_refused_not_a_crash(server):
    port, _ = server
    r = raw(port, b"GET /api/admin HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer \xc3\xa9\xc3\xa9\r\nConnection: close\r\n\r\n")
    assert "401" in status(r)
    r = raw(port, b"POST /api/wa/inbound HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer \xc3\xa9\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}")
    assert "401" in status(r)


def test_same_secret_never_raises():
    assert same_secret("abc", "abc") and not same_secret("abd", "abc") and not same_secret("", "abc")
    assert not same_secret("é", "abc") and not same_secret("abc", "") and not same_secret("x" * 5000, "abc")


@pytest.mark.parametrize("length", ["abc", "-1", "1e3", "+5", " ", "5.0", "٣"])
def test_a_bad_content_length_is_a_400_not_a_hang(server, length):
    port, _ = server
    assert "400" in status(post(port, "/api/chat", b'{"message":"hi"}', length=length))
    assert "400" in status(post(port, "/api/wa/inbound", b"{}", length=length, auth="wa-token-123"))
    assert "400" in status(post(port, "/api/voice/transcribe", b"x", length=length))        # a raw-body route


def test_json_that_is_not_an_object_or_has_a_bad_date_is_a_400(server):
    port, _ = server
    for body in (b"[]", b"nope", b'{"date": 20261007}', b'{"date": ["x"]}', b"[" * 5000):
        assert "400" in status(post(port, "/api/chat", body)), body[:20]


def test_an_unexpected_error_is_a_plain_500_that_says_nothing(server, monkeypatch, caplog):
    port, _ = server

    def boom(req):
        raise TypeError("secret detail: sk-or-v1-LEAK")
    monkeypatch.setitem(routes.POST_ROUTES, "/api/test-boom", boom)
    monkeypatch.setitem(routes.GET_ROUTES, "/api/test-boom", boom)
    for r in (post(port, "/api/test-boom"),
              raw(port, f"GET /api/test-boom HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer {TOKEN}\r\nConnection: close\r\n\r\n".encode())):
        assert "500" in status(r) and b"LEAK" not in r and b"secret detail" not in r and json.loads(r.split(b"\r\n\r\n")[1]) == {"error": "server error"}
    assert "sk-or-v1-LEAK" not in caplog.text and "TypeError" in caplog.text           # the log has the type, not the text


def test_a_value_error_is_still_the_callers_400(server, monkeypatch):
    port, _ = server
    monkeypatch.setitem(routes.POST_ROUTES, "/api/test-bad", lambda req: (_ for _ in ()).throw(ValueError("name too long")))
    r = post(port, "/api/test-bad")
    assert "400" in status(r) and b"name too long" in r


def test_security_headers_on_pages_and_api_answers(server):
    port, _ = server
    for r in (raw(port, b"GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"),
              raw(port, b"GET /api/lesson HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")):
        head = r.split(b"\r\n\r\n")[0].decode().lower()
        assert "x-frame-options: deny" in head and "referrer-policy: no-referrer" in head and "cache-control: no-store" in head
        assert "frame-ancestors 'none'" in head and "base-uri 'none'" in head and "form-action 'self'" in head
        assert "x-content-type-options: nosniff" in head


def test_a_half_sent_request_is_dropped_after_the_timeout(server):
    port, handler = server
    assert handler.timeout == 60
    handler.timeout = 0.5            # the class is shared by the running server: new connections use the short limit
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(b"GET /api/lesson HTT")
    time.sleep(1.5)
    s.settimeout(3)
    start = time.time()
    try:
        data = s.recv(100)                               # the server gave up and closed: an empty read, at once
    except OSError:
        data = None
    assert data == b"" and time.time() - start < 2       # (a socket.timeout here would mean it was still holding the thread)
    s.close()


def test_a_short_token_is_refused_at_start(tmp_path):
    app = App(load_pack(PACKS, "security-plus-sy0-701", tmp_path), Store(tmp_path / "t.db"), tmp_path, token="x" * (MIN_TOKEN - 1))
    with pytest.raises(SystemExit, match="too short"):
        serve(app, "127.0.0.1", 0)
    with pytest.raises(SystemExit, match="without TUTOR_TOKEN"):
        serve(App(load_pack(PACKS, "security-plus-sy0-701", tmp_path), Store(tmp_path / "t2.db"), tmp_path, token=None), "0.0.0.0", 0)
