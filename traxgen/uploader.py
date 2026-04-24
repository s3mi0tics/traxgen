"""Upload a POWER_2022 .course binary to Ravensburger's share-code endpoint.

Posts `multipart/form-data` to https://gravitrax.link.ravensburger.com/api/upload/
with headers that match the real iOS GraviTrax app (v2.8.0.31080908, Unity
6000.0.66f2). On success the server returns `{"code": "<10-char-code>"}` and
`upload_course` returns that code.

The server deduplicates by content hash — uploading identical bytes twice
returns the same code. Probe evidence (2026-04-24) indicates the server
performs no content validation at upload time: a truncated 100-byte payload
was accepted with status 200 and returned a fresh code. Any HTTP error
encountered in practice is therefore transport-level, not payload-level.
`UploadClientError` and `UploadServerError` exist for completeness in case
that ever changes.

Stdlib-only (no `requests` dependency). See docs/refs/upload-api.md for the
reverse-engineered endpoint specification.

Path: traxgen/traxgen/uploader.py
"""

from __future__ import annotations

import json
import uuid
from typing import Final
from urllib import error as urllib_error
from urllib import request as urllib_request

# --- Endpoint and headers --------------------------------------------------

UPLOAD_URL: Final[str] = "https://gravitrax.link.ravensburger.com/api/upload/"

# Hardcoded to match the real iOS GraviTrax app captured 2026-04-24.
# `x-unity-version` and `user-agent` required-ness is untested — safer to
# send what the app sends. See docs/refs/upload-api.md.
_UNITY_VERSION: Final[str] = "6000.0.66f2"
_USER_AGENT: Final[str] = "GraviTrax/2.8.0.31080908 CFNetwork/3860.400.51 Darwin/25.3.0"

# Multipart part metadata. Filename is `course.trax` on the wire even though
# the format is identical to a `.course` file — this matches the real app.
_FORM_FIELD_NAME: Final[str] = "file"
_FORM_FILENAME: Final[str] = "course.trax"


# --- Exception hierarchy ---------------------------------------------------

class UploadError(Exception):
    """Base for every failure mode of upload_course()."""


class UploadClientError(UploadError):
    """Server returned 4xx — request rejected (malformed, too large, etc.)."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"upload rejected by server (HTTP {status}): {body[:200]}")


class UploadServerError(UploadError):
    """Server returned 5xx — server-side failure, possibly transient."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"upload failed server-side (HTTP {status}): {body[:200]}")


class UploadMalformedResponseError(UploadError):
    """Server returned 2xx but the response body wasn't the expected JSON shape."""

    def __init__(self, body: str, reason: str) -> None:
        self.body = body
        self.reason = reason
        super().__init__(f"malformed upload response ({reason}): {body[:200]}")


class UploadNetworkError(UploadError):
    """Network-level failure — DNS, TLS, connection, timeout."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"network failure during upload: {reason}")


# --- Internals -------------------------------------------------------------

def _generate_boundary(payload: bytes) -> str:
    """Return a multipart boundary guaranteed not to collide with the payload.

    UUID hex is 128 bits of randomness — collision with any given byte
    sequence is astronomically unlikely, but not structurally impossible.
    We check and regenerate rather than pretend it can't happen.
    """
    while True:
        boundary = f"----traxgen{uuid.uuid4().hex}"
        if boundary.encode("ascii") not in payload:
            return boundary


def _build_multipart_body(binary: bytes, boundary: str) -> bytes:
    """Assemble a multipart/form-data body with a single `file` part.

    Matches the wire format sent by the real iOS app: one part named `file`
    with filename `course.trax` and content-type `application/octet-stream`,
    raw binary bytes, closing boundary with trailing `--`.
    """
    return b"".join([
        f"--{boundary}\r\n".encode("ascii"),
        (
            f'Content-Disposition: form-data; name="{_FORM_FIELD_NAME}"; '
            f'filename="{_FORM_FILENAME}"\r\n'
        ).encode("ascii"),
        b"Content-Type: application/octet-stream\r\n\r\n",
        binary,
        f"\r\n--{boundary}--\r\n".encode("ascii"),
    ])


def _parse_success_response(body_bytes: bytes) -> str:
    """Extract the share code from a 2xx response body, or raise UploadMalformedResponseError."""
    try:
        body_text = body_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadMalformedResponseError(
            body=body_bytes.decode("utf-8", errors="replace"),
            reason=f"response not valid UTF-8: {exc}",
        ) from exc

    try:
        parsed = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise UploadMalformedResponseError(
            body=body_text, reason=f"response not valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(parsed, dict):
        raise UploadMalformedResponseError(
            body=body_text,
            reason=f"expected JSON object, got {type(parsed).__name__}",
        )

    code = parsed.get("code")
    if not isinstance(code, str) or not code:
        raise UploadMalformedResponseError(
            body=body_text, reason="response missing non-empty 'code' field"
        )

    return code


# --- Public API ------------------------------------------------------------

def upload_course(binary: bytes, *, timeout: float = 30.0) -> str:
    """Upload a course binary and return the assigned share code.

    Args:
        binary: Raw bytes of a POWER_2022 .course file.
        timeout: Per-request timeout in seconds (default 30.0).

    Returns:
        The 10-character share code assigned by the server.

    Raises:
        UploadClientError: Server returned 4xx.
        UploadServerError: Server returned 5xx.
        UploadMalformedResponseError: Server returned 2xx but the body was not
            the expected `{"code": "..."}` JSON shape.
        UploadNetworkError: DNS, TLS, connection, or timeout failure.
    """
    boundary = _generate_boundary(binary)
    body = _build_multipart_body(binary, boundary)

    req = urllib_request.Request(
        UPLOAD_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "x-unity-version": _UNITY_VERSION,
            "user-agent": _USER_AGENT,
            "accept": "*/*",
        },
    )

    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            response_body = resp.read()
    except urllib_error.HTTPError as exc:
        # HTTPError is raised for 4xx/5xx. `.read()` gives the response body.
        status = exc.code
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # best-effort body read
            error_body = ""
        if 400 <= status < 500:
            raise UploadClientError(status=status, body=error_body) from exc
        if 500 <= status < 600:
            raise UploadServerError(status=status, body=error_body) from exc
        # Some other non-2xx (1xx, 3xx) that urllib surfaced as HTTPError.
        # Treat as a malformed response — we expected 2xx.
        raise UploadMalformedResponseError(
            body=error_body, reason=f"unexpected HTTP status {status}"
        ) from exc
    except urllib_error.URLError as exc:
        # URLError covers DNS, connection refused, TLS failures, and timeouts
        # surfaced as socket.timeout under the hood.
        raise UploadNetworkError(reason=str(exc.reason)) from exc
    except TimeoutError as exc:
        # Python 3.10+ raises TimeoutError from socket-level timeouts even
        # outside URLError in some paths. Map to the same network bucket.
        raise UploadNetworkError(reason=f"timeout: {exc}") from exc

    return _parse_success_response(response_body)
