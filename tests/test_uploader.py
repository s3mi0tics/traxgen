"""Unit tests for traxgen.uploader against an in-process mock HTTP server.

The mock server is a threading HTTPServer bound to 127.0.0.1 on a random
port. Each test instantiates it with a request handler that records the
incoming request (URL, method, headers, body) and responds according to
the test's needs. This lets us assert the full wire shape — headers,
multipart structure, payload integrity — without touching the real
Ravensburger endpoint. One live-endpoint canary lives at the bottom,
gated by the `network` pytest marker.

Path: traxgen/tests/test_uploader.py
"""

from __future__ import annotations

import re
import threading
import uuid as stdlib_uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from traxgen import uploader
from traxgen.uploader import (
    UPLOAD_RETRY_ATTEMPTS,
    UPLOAD_RETRY_BACKOFF_SECONDS,
    UploadClientError,
    UploadMalformedResponseError,
    UploadNetworkError,
    UploadServerError,
    upload_course,
    upload_course_with_retry,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --- Mock server plumbing --------------------------------------------------

@dataclass
class CapturedRequest:
    """What the mock server saw on the wire for a single request."""
    path: str = ""
    method: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


@dataclass
class MockResponse:
    """What the mock server should send back."""
    status: int = 200
    body: bytes = b'{"code":"MOCKCODE01"}'
    content_type: str = "application/json"


def _make_handler(
    captured: CapturedRequest, response: MockResponse
) -> type[BaseHTTPRequestHandler]:
    """Build a BaseHTTPRequestHandler class that captures POST and returns `response`."""

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            captured.path = self.path
            captured.method = self.command
            # headers is a Message; lowercase the keys for easy assertion
            captured.headers = {k.lower(): v for k, v in self.headers.items()}
            length = int(self.headers.get("Content-Length", "0"))
            captured.body = self.rfile.read(length) if length > 0 else b""

            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def log_message(self, format: str, *args: object) -> None:
            # Silence the default stderr logging during tests.
            return

    return _Handler


@dataclass
class MockServerHandle:
    """Handle returned by the mock_server fixture."""
    url: str
    captured: CapturedRequest
    response: MockResponse


@pytest.fixture
def mock_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[MockServerHandle]:
    """Spin up a local HTTP server, patch uploader.UPLOAD_URL to point at it, tear down on exit.

    The handle lets the test mutate `response` before calling `upload_course`
    and inspect `captured` afterwards.
    """
    captured = CapturedRequest()
    response = MockResponse()

    handler_cls = _make_handler(captured, response)
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/api/upload/"
    monkeypatch.setattr(uploader, "UPLOAD_URL", url)

    try:
        yield MockServerHandle(url=url, captured=captured, response=response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --- Happy-path wire shape -------------------------------------------------

def test_upload_course_returns_share_code(mock_server: MockServerHandle) -> None:
    """upload_course returns the `code` string from a well-formed 200 response."""
    mock_server.response.body = b'{"code":"ABCDEF1234"}'
    assert upload_course(b"binary payload") == "ABCDEF1234"


def test_upload_course_posts_to_upload_url(mock_server: MockServerHandle) -> None:
    """Request method is POST and path matches the configured endpoint."""
    upload_course(b"payload")
    assert mock_server.captured.method == "POST"
    assert mock_server.captured.path == "/api/upload/"


def test_upload_course_sends_unity_version_header(mock_server: MockServerHandle) -> None:
    """x-unity-version matches the real iOS app value."""
    upload_course(b"payload")
    assert mock_server.captured.headers["x-unity-version"] == "6000.0.66f2"


def test_upload_course_sends_user_agent_header(mock_server: MockServerHandle) -> None:
    """user-agent matches the real iOS app value."""
    upload_course(b"payload")
    ua = mock_server.captured.headers["user-agent"]
    assert "GraviTrax/" in ua
    assert "CFNetwork/" in ua
    assert "Darwin/" in ua


def test_upload_course_sends_multipart_content_type(mock_server: MockServerHandle) -> None:
    """content-type is multipart/form-data with a boundary parameter."""
    upload_course(b"payload")
    ct = mock_server.captured.headers["content-type"]
    assert ct.startswith("multipart/form-data; boundary=")


# --- Multipart body shape --------------------------------------------------

def _boundary_from(content_type: str) -> str:
    """Extract the boundary= parameter from a content-type header."""
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;\s]+))", content_type)
    assert match is not None, f"no boundary in content-type: {content_type}"
    return match.group(1) or match.group(2)


def test_upload_course_body_uses_single_file_part(mock_server: MockServerHandle) -> None:
    """Body has exactly one part, named `file`, with filename `course.trax`."""
    upload_course(b"payload")
    boundary = _boundary_from(mock_server.captured.headers["content-type"])
    body = mock_server.captured.body
    # Split on the boundary delimiter. Including the leading CRLF keeps us
    # from fencepost errors on the first part.
    parts = body.split(f"--{boundary}".encode("ascii"))
    # parts[0] is the pre-boundary preamble (empty), parts[-1] is the closing
    # boundary with trailing `--\r\n`, anything between is a form field.
    form_parts = [p for p in parts[1:-1] if p.strip()]
    assert len(form_parts) == 1, f"expected 1 form part, got {len(form_parts)}"
    headers_blob = form_parts[0].split(b"\r\n\r\n", 1)[0].decode("ascii")
    assert 'name="file"' in headers_blob
    assert 'filename="course.trax"' in headers_blob
    assert "Content-Type: application/octet-stream" in headers_blob


def test_upload_course_preserves_payload_bytes(mock_server: MockServerHandle) -> None:
    """The exact bytes given to upload_course appear verbatim in the multipart body."""
    payload = bytes(range(256)) * 4  # 1024 bytes covering every byte value
    upload_course(payload)
    boundary = _boundary_from(mock_server.captured.headers["content-type"])
    body = mock_server.captured.body
    parts = body.split(f"--{boundary}".encode("ascii"))
    form_parts = [p for p in parts[1:-1] if p.strip()]
    assert len(form_parts) == 1
    # Split headers from payload within the single part.
    _, part_body = form_parts[0].split(b"\r\n\r\n", 1)
    # Strip the trailing CRLF that separates the payload from the next boundary.
    if part_body.endswith(b"\r\n"):
        part_body = part_body[:-2]
    assert part_body == payload


def test_boundary_regenerates_on_payload_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_generate_boundary loops if the first candidate appears in the payload.

    This is tested against the private helper directly. `uuid.uuid4().hex` is
    monkeypatched to return a colliding value once, then a fresh value — the
    function must skip the first and return the second.
    """
    hex_values = iter(["deadbeef" * 4, "cafebabe" * 4])
    calls: list[str] = []

    class _FakeUUID:
        def __init__(self, hex_value: str) -> None:
            self.hex = hex_value

    def _fake_uuid4() -> _FakeUUID:
        value = next(hex_values)
        calls.append(value)
        return _FakeUUID(value)

    monkeypatch.setattr(stdlib_uuid, "uuid4", _fake_uuid4)
    # Payload contains the first boundary candidate (ASCII bytes), forcing a regen.
    colliding = b"----traxgen" + (b"deadbeef" * 4)
    payload = b"junk before " + colliding + b" junk after"
    boundary = uploader._generate_boundary(payload)
    assert boundary == "----traxgencafebabecafebabecafebabecafebabe"
    assert len(calls) == 2, "expected exactly one regeneration"


# --- Response parsing ------------------------------------------------------

def test_upload_course_raises_on_non_json_body(mock_server: MockServerHandle) -> None:
    """A 200 with a non-JSON body surfaces as UploadMalformedResponseError."""
    mock_server.response.body = b"not json at all"
    with pytest.raises(UploadMalformedResponseError, match="not valid JSON"):
        upload_course(b"payload")


def test_upload_course_raises_on_non_object_json(mock_server: MockServerHandle) -> None:
    """A 200 with JSON that isn't an object surfaces as UploadMalformedResponseError."""
    mock_server.response.body = b'["not","an","object"]'
    with pytest.raises(UploadMalformedResponseError, match="expected JSON object"):
        upload_course(b"payload")


def test_upload_course_raises_on_missing_code_field(mock_server: MockServerHandle) -> None:
    """A 200 with JSON missing the `code` key surfaces as UploadMalformedResponseError."""
    mock_server.response.body = b'{"notcode": "VU73AWP5AO"}'
    with pytest.raises(UploadMalformedResponseError, match="missing non-empty 'code'"):
        upload_course(b"payload")


def test_upload_course_raises_on_empty_code(mock_server: MockServerHandle) -> None:
    """A 200 with an empty code string surfaces as UploadMalformedResponseError."""
    mock_server.response.body = b'{"code": ""}'
    with pytest.raises(UploadMalformedResponseError, match="missing non-empty 'code'"):
        upload_course(b"payload")


def test_upload_course_raises_on_non_string_code(mock_server: MockServerHandle) -> None:
    """A 200 where `code` is not a string surfaces as UploadMalformedResponseError."""
    mock_server.response.body = b'{"code": 42}'
    with pytest.raises(UploadMalformedResponseError, match="missing non-empty 'code'"):
        upload_course(b"payload")


# --- HTTP error mapping ----------------------------------------------------

def test_upload_course_raises_client_error_on_4xx(mock_server: MockServerHandle) -> None:
    """A 4xx response surfaces as UploadClientError with status and body preserved."""
    mock_server.response.status = 400
    mock_server.response.body = b"bad request from server"
    mock_server.response.content_type = "text/plain"
    with pytest.raises(UploadClientError) as exc_info:
        upload_course(b"payload")
    assert exc_info.value.status == 400
    assert "bad request from server" in exc_info.value.body


def test_upload_course_raises_server_error_on_5xx(mock_server: MockServerHandle) -> None:
    """A 5xx response surfaces as UploadServerError with status and body preserved."""
    mock_server.response.status = 503
    mock_server.response.body = b"service unavailable"
    mock_server.response.content_type = "text/plain"
    with pytest.raises(UploadServerError) as exc_info:
        upload_course(b"payload")
    assert exc_info.value.status == 503
    assert "service unavailable" in exc_info.value.body


# --- Network-level failures ------------------------------------------------

def test_upload_course_raises_network_error_on_connection_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection-refused failure surfaces as UploadNetworkError.

    We point the uploader at a port that is almost certainly unbound
    (127.0.0.1:1) — not a perfect guarantee, but reliable in practice.
    """
    monkeypatch.setattr(uploader, "UPLOAD_URL", "http://127.0.0.1:1/api/upload/")
    with pytest.raises(UploadNetworkError):
        upload_course(b"payload", timeout=2.0)


# --- Live-endpoint canary --------------------------------------------------

@pytest.mark.network
def test_upload_course_against_live_endpoint_returns_code() -> None:
    """Live canary: uploading GDZJZA3J3T.course returns a 10-char share code.

    Because the server deduplicates by content hash, this should reliably
    return `GDZJZA3J3T` itself. We don't hard-assert that specific value —
    if Ravensburger ever changes its dedup scheme we'd rather the test
    still pass on "looks like a valid code" — but the shape is stable.

    Run manually: `uv run pytest -m network`.
    """
    course_bytes = (FIXTURES_DIR / "GDZJZA3J3T.course").read_bytes()
    code = upload_course(course_bytes)
    assert isinstance(code, str)
    assert len(code) == 10
    assert code.isalnum()


# --- Retrying the endpoint's transient failures ----------------------------
#
# Added 2026-08-23 (s23) after an SSL handshake timeout took out two of seven
# cells in one probe run -- both controls among them -- voiding the campaign.
# Fourth firing of observations #15.


class FakeUpload:
    """Fails with a scripted sequence of errors, then succeeds.

    Records the timeout it was handed, so a test can prove the retry does not
    quietly change the caller's parameters between attempts.
    """

    def __init__(self, *, errors: list[Exception], code: str = "ABCDE12345") -> None:
        self.errors = list(errors)
        self.code = code
        self.calls = 0
        self.timeouts: list[float] = []

    def __call__(self, binary: bytes, *, timeout: float) -> str:
        self.calls += 1
        self.timeouts.append(timeout)
        if self.errors:
            raise self.errors.pop(0)
        return self.code


class FakeSleep:
    """Records delays without spending them."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def test_a_clean_upload_costs_one_attempt_and_no_sleep() -> None:
    """The happy path must not pay for the retry policy existing."""
    upload, sleep = FakeUpload(errors=[]), FakeSleep()
    code, attempts = upload_course_with_retry(b"x", upload=upload, sleep=sleep)
    assert (code, attempts) == ("ABCDE12345", 1)
    assert sleep.delays == []


def test_a_server_error_is_retried_and_can_succeed() -> None:
    """The HTTP 520 case: three campaigns, three firings, always transient."""
    upload = FakeUpload(errors=[UploadServerError(status=520, body="")])
    sleep = FakeSleep()
    code, attempts = upload_course_with_retry(b"x", upload=upload, sleep=sleep)
    assert (code, attempts) == ("ABCDE12345", 2)
    assert sleep.delays == [2.0]


def test_a_network_error_is_retried_and_can_succeed() -> None:
    """The 2026-08-23 case: `_ssl.c:993: The handshake operation timed out`."""
    upload = FakeUpload(errors=[UploadNetworkError(reason="handshake timed out")])
    sleep = FakeSleep()
    code, attempts = upload_course_with_retry(b"x", upload=upload, sleep=sleep)
    assert (code, attempts) == ("ABCDE12345", 2)


def test_a_client_error_is_not_retried() -> None:
    """4xx is the payload being wrong. Retrying it is a slower no, not a fix."""
    upload = FakeUpload(errors=[UploadClientError(status=400, body="bad")])
    sleep = FakeSleep()
    with pytest.raises(UploadClientError):
        upload_course_with_retry(b"x", upload=upload, sleep=sleep)
    assert upload.calls == 1
    assert sleep.delays == []


def test_a_malformed_response_is_not_retried() -> None:
    """Never fired. A policy for it would be invention, not evidence."""
    upload = FakeUpload(
        errors=[UploadMalformedResponseError(body="?", reason="no code in body")]
    )
    with pytest.raises(UploadMalformedResponseError):
        upload_course_with_retry(b"x", upload=upload, sleep=FakeSleep())
    assert upload.calls == 1


def test_it_gives_up_after_the_declared_attempts_and_raises_the_last_error() -> None:
    """Bounded. An unbounded retry is the silent-hang failure of observations #25."""
    errors = [
        UploadServerError(status=520, body=""),
        UploadNetworkError(reason="first timeout"),
        UploadNetworkError(reason="final timeout"),
    ]
    upload, sleep = FakeUpload(errors=errors), FakeSleep()
    with pytest.raises(UploadNetworkError, match="final timeout"):
        upload_course_with_retry(b"x", upload=upload, sleep=sleep)
    assert upload.calls == UPLOAD_RETRY_ATTEMPTS == 3
    assert sleep.delays == [2.0, 6.0]


def test_the_backoff_table_covers_every_gap_between_attempts() -> None:
    """Guards an off-by-one that would IndexError only on the last retry.

    With N attempts there are N-1 gaps. If someone raises ATTEMPTS without
    extending the table, the failure appears solely on a run that already
    failed twice -- the least observable place for a crash to hide.
    """
    assert len(UPLOAD_RETRY_BACKOFF_SECONDS) == UPLOAD_RETRY_ATTEMPTS - 1


def test_the_retry_does_not_alter_the_timeout_between_attempts() -> None:
    """Each attempt gets the caller's timeout, not a mutated one."""
    upload = FakeUpload(errors=[UploadServerError(status=502, body="")])
    upload_course_with_retry(b"x", timeout=12.5, upload=upload, sleep=FakeSleep())
    assert upload.timeouts == [12.5, 12.5]
