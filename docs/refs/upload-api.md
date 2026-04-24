<!-- docs/refs/upload-api.md -->

# GraviTrax Share-Code Upload API

Undocumented REST endpoint used by the official GraviTrax iOS app to
register a local course and receive a shareable 10-character code.
Reverse-engineered by HTTPS interception (mitmproxy) on the iOS app.
Not affiliated with Ravensburger; behavior may change without notice.

This is the **upload** half of the share-code API. The **download**
half (`/api/download/{code}`) is already implemented by
[lfrancke/murmelbahn](https://github.com/lfrancke/murmelbahn).

---

## Endpoint

`POST https://gravitrax.link.ravensburger.com/api/upload/`

The trailing slash matters — requests to `/api/upload` (no slash)
have not been tested and may 301/404.

Host is behind Cloudflare (`server: cloudflare`, `cf-cache-status: DYNAMIC`,
`cf-ray` header returned). HSTS enforced
(`strict-transport-security: max-age=31536000; includeSubdomains`).

## Request

### Required headers

| Header | Value | Source |
|---|---|---|
| `content-type` | `multipart/form-data; boundary="<boundary>"` | Standard multipart |
| `x-unity-version` | `6000.0.66f2` | Sent by real app; likely required |
| `user-agent` | `GraviTrax/2.8.0.31080908 CFNetwork/3860.400.51 Darwin/25.3.0` | Sent by real app; required-ness untested |
| `accept` | `*/*` | Sent by real app |

The `x-unity-version` header is non-standard. The real app is built
with Unity 6000.0.66f2 and sends it on every request. Whether the
server checks it is untested — a useful experiment for a future
session is to try the endpoint without it and see what fails.

The `user-agent` was sent by the real app as shown above. A successful
upload has been verified using that exact value. Whether the server
would accept a different user-agent is untested.

No authentication. No auth token, no cookie, no session — consistent
with Ravensburger's privacy policy (Feb 2026) which states course
sharing is anonymous.

### Body

`multipart/form-data` with a single part:

- **Name:** `file`
- **Filename:** `course.trax`
- **Content-Type:** `application/octet-stream`
- **Body:** raw binary bytes of the course file (POWER_2022 format).
  Not base64-encoded, not transformed — literal bytes.

Note the filename is `course.trax`, not `course.course`. Same binary
format, different extension on the wire.

### Example request body

Raw wire format (CRLF line endings):

    --<boundary>
    Content-Type: application/octet-stream
    Content-Disposition: form-data; name="file"; filename="course.trax"

    <raw binary course bytes>
    --<boundary>--

## Response

`200 OK` with JSON body:

    {"code": "VU73AWP5AO"}

The code is a 10-character string, appears to use uppercase letters
and digits (base 36-ish, but character set not formally documented).

`content-type: application/json`. Response body is brotli-encoded
(`content-encoding: br`) — stdlib `urllib` handles this transparently
on Python 3.12+; if using `urllib` on older Python or if
`content-encoding` parsing is disabled, the `br` decoding must be
handled manually.

### Deduplication

The server appears to deduplicate by content hash. Uploading the same
binary twice returns the same share code both times. This was
confirmed empirically: re-uploading the GDZJZA3J3T.course fixture
(which came from a prior download of share code `GDZJZA3J3T`)
returned `{"code": "GDZJZA3J3T"}`.

Implications:
- Safe to re-upload for testing without polluting the database.
- A generator producing the same course twice gets the same code,
  which is a nice idempotency property.
- To get a *new* code, the binary bytes must be distinct (even a
  single-byte change to the course GUID or creation timestamp
  should suffice, though this is untested).

## Error behavior

Untested. We do not yet know what the server returns for:
- Invalid binary (malformed POWER_2022 payload)
- Oversized payload (limit unknown)
- Missing required headers
- Rate limiting
- Unsupported schema versions

Whoever implements the full traxgen uploader should exercise at least
the first two of these to learn the error shapes before writing
error-handling code.

## Prior art

- `lfrancke/murmelbahn/lib/src/app/download.rs` — Rust implementation
  of the download half (`GET /api/download/{code}`). No upload
  implementation anywhere in open source as of April 2026.

## Ethics & rate limiting

- Ravensburger's privacy policy explicitly allows anonymous sharing,
  so uploading a course is not a TOS violation.
- Repeated uploads of the same content are server-side deduped, so
  they cost nothing. But repeated uploads of *different* content
  grow Ravensburger's database. Don't hammer the endpoint in tests.
- Prefer a local mock server for automated testing. Reserve live-
  endpoint tests for manual verification, gated behind the existing
  `network` pytest marker.

## Provenance

Captured April 24, 2026, from a real GraviTrax iOS app (v2.8.0.31080908)
running on iOS 18.7. Captured via mitmproxy on a developer Mac with
the mitmproxy CA cert installed in the iPhone's system trust store.
The app does **not** pin certs — the request decrypts cleanly without
any bypass work.
