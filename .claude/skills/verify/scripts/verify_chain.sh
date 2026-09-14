#!/usr/bin/env bash
# Run traxgen's verification chain once and leave the evidence on disk.
#
#   .claude/skills/verify/scripts/verify_chain.sh [--board single-plate|standard-square]
#       [--measured-only] [--no-upload] [--render]
#   .claude/skills/verify/scripts/verify_chain.sh --doctor
#
# Stages, each a PASS/FAIL line in summary.txt:
#   generate      python -m traxgen generate (strict validation inside it)
#   determinism   a second generate produces identical bytes
#   pin           single-plate only: bytes match the Phase 1 sha256
#   check         check_course.py: byte round trip + full validator
#   upload        share code from Ravensburger's endpoint (network, public)
#   code_pin      single-plate only: code is KN6F459ZR3 (endpoint dedups by content)
#   render        opt-in: app play-button oracle on a cold-booted emulator
#
# Evidence: verify-runs/<UTC stamp>-<board>[-measured]-<4 chars>/ at the repo root (gitignored).
# Exit: 0 every run stage passed; 1 a stage failed; 3 generator refused
# (expected for --measured-only on a board with no measured placement); 2 usage.

set -u
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 2
HERE=.claude/skills/verify/scripts

# Phase 1's closing artifact (plan.md, 2026-09-07): 177 bytes, rendered active.
PIN_SHA=1ede9be9e5a843b1f09576837be8e80c4c2f579d5eb1a331aed99cc49ff7db1c
PIN_CODE=KN6F459ZR3

board=single-plate measured="" upload=1 render=0
while [ $# -gt 0 ]; do
  case "$1" in
    --board) board="${2:?--board needs a value}"; shift 2 ;;
    --measured-only) measured=--measured-only; shift ;;
    --no-upload) upload=0; shift ;;
    --render) render=1; shift ;;
    --doctor) exec uv run python "$HERE/doctor.py" ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ "$render" = 1 ] && [ "$upload" = 0 ] && { echo "--render needs an upload" >&2; exit 2; }

# mktemp's suffix keeps two runs in the same second from sharing (and
# overwriting) one evidence directory.
mkdir -p verify-runs
run=$(mktemp -d "verify-runs/$(date -u +%Y%m%dT%H%M%SZ)-$board${measured:+-measured}-XXXX") || exit 2
summary="$run/summary.txt"
failed=0
record() { echo "$1 $2 $3" | tee -a "$summary"; [ "$1" = FAIL ] && failed=1; return 0; }

echo "run $run  head $(git rev-parse --short HEAD)  board $board ${measured}" >"$summary"

uv run python -m traxgen generate --set vertical-starter --board "$board" $measured \
  --out "$run/course.course" >"$run/generate.log" 2>&1
gen=$?
if [ "$gen" = 3 ]; then
  record REFUSED generate "generator refused (exit 3), see generate.log"
  exit 3
fi
[ "$gen" = 0 ] || { record FAIL generate "exit $gen, see generate.log"; exit 1; }
record PASS generate "$(head -1 "$run/generate.log" | sed 's/ to .*//'); $(grep '^claim:' "$run/generate.log")"

uv run python -m traxgen generate --set vertical-starter --board "$board" $measured \
  --out "$run/course.again.course" >/dev/null 2>&1
if cmp -s "$run/course.course" "$run/course.again.course"; then
  record PASS determinism "two generates, identical bytes"
else
  record FAIL determinism "two generates differ"
fi

sha=$(shasum -a 256 "$run/course.course" | cut -d' ' -f1)
if [ "$board" = single-plate ] && [ -z "$measured" ]; then
  [ "$sha" = "$PIN_SHA" ] && record PASS pin "sha256 matches Phase 1 bytes" \
                          || record FAIL pin "sha256 $sha, expected $PIN_SHA"
fi

uv run python "$HERE/check_course.py" "$run/course.course" >"$run/check.log" 2>&1
if [ $? = 0 ]; then
  record PASS check "$(grep -c '^WARNING' "$run/check.log") warnings; $(grep '^claim:' "$run/check.log")"
else
  record FAIL check "see check.log"
fi

if [ "$upload" = 1 ] && [ "$failed" = 0 ]; then
  code=$(uv run python -m scripts.upload_course "$run/course.course" 2>"$run/upload.log")
  if [ $? = 0 ]; then
    echo "$code" >"$run/share_code.txt"
    record PASS upload "$code"
    if [ "$board" = single-plate ] && [ -z "$measured" ]; then
      [ "$code" = "$PIN_CODE" ] && record PASS code_pin "matches the app-certified code" \
                                || record FAIL code_pin "got $code, expected $PIN_CODE"
    fi
  else
    record FAIL upload "see upload.log"
  fi
fi

if [ "$render" = 1 ] && [ "$failed" = 0 ]; then
  shot=$(uv run python -m scripts.render_course "$code" --fresh --detect-validity \
         --screenshot-dir "$run" --name "rendered_$code" 2>"$run/render.log")
  verdict=$(sed -n 's/^play button: //p' "$run/render.log")
  if [ -n "$shot" ] && [ "$verdict" = active ]; then
    record PASS render "play button active ($shot)"
  else
    record FAIL render "play button '${verdict:-none}', see render.log"
  fi
fi

echo "evidence: $run"
exit "$failed"
