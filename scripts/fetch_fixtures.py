"""
Fetch GraviTrax course files from murmelbahn.fly.dev for use as test fixtures.

Downloads three formats per course:
  {code}.course     raw binary         (parse target)
  {code}.dump.txt   human-readable     (oracle for parser output)
  {code}.bom.json   bill of materials  (oracle for piece counts)

Fetches skip files that already exist; pass --force to re-download.
Never called implicitly by tests — fixture generation is an explicit step.

Path: traxgen/scripts/fetch_fixtures.py
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://murmelbahn.fly.dev/api/course"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
USER_AGENT = "traxgen-fetch-fixtures/0.1 (+https://github.com/s3mi0tics/traxgen)"

# Known-good course codes. Expand as we discover interesting fixtures.
DEFAULT_CODES: tuple[str, ...] = ("GDZJZA3J3T",)

# (url_suffix, local_extension, is_binary)
FORMATS: tuple[tuple[str, str, bool], ...] = (
    ("raw", ".course", True),
    ("dump", ".dump.txt", False),
    ("bom?format=json", ".bom.json", False),
)


def fetch_course(code: str, dest_dir: Path, *, force: bool) -> int:
    """Fetch all three formats for one course. Returns the number of failed fetches."""
    failures = 0
    for url_suffix, ext, is_binary in FORMATS:
        dest = dest_dir / f"{code}{ext}"
        if dest.exists() and not force:
            print(f"  skip  {dest.name} (exists)")
            continue

        url = f"{BASE_URL}/{code}/{url_suffix}"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "").lower()
                raw = response.read()
        except urllib.error.HTTPError as exc:
            print(f"  FAIL  {dest.name} — HTTP {exc.code} from {url}", file=sys.stderr)
            failures += 1
            continue
        except urllib.error.URLError as exc:
            print(f"  FAIL  {dest.name} — {exc.reason} from {url}", file=sys.stderr)
            failures += 1
            continue

        # Guard against SPA catch-all or error pages returning HTML with 200 OK
        if "text/html" in content_type:
            print(
                f"  FAIL  {dest.name} — got text/html from {url} "
                f"(endpoint likely moved; not writing file)",
                file=sys.stderr,
            )
            failures += 1
            continue

        if is_binary:
            dest.write_bytes(raw)
        else:
            text = raw.decode("utf-8")
            # Pretty-print JSON so diffs are readable in git
            if ext == ".bom.json":
                try:
                    text = json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
                except json.JSONDecodeError as exc:
                    print(
                        f"  FAIL  {dest.name} — invalid JSON from {url}: {exc}",
                        file=sys.stderr,
                    )
                    failures += 1
                    continue
            dest.write_text(text, encoding="utf-8")

        print(f"  ok    {dest.name} ({dest.stat().st_size:,} bytes)")
    return failures


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch GraviTrax course files from murmelbahn as test fixtures.",
    )
    parser.add_argument(
        "codes",
        nargs="*",
        help="Course codes to fetch. Defaults to DEFAULT_CODES if omitted.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the destination file already exists.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=FIXTURES_DIR,
        help=f"Destination directory (default: {FIXTURES_DIR}).",
    )
    args = parser.parse_args()

    codes = args.codes or list(DEFAULT_CODES)
    args.dest.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {len(codes)} course(s) into {args.dest}")
    total_failures = 0
    for code in codes:
        print(f"\n{code}")
        total_failures += fetch_course(code, args.dest, force=args.force)

    print(f"\nDone. {total_failures} failure(s).")
    return 0 if total_failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
