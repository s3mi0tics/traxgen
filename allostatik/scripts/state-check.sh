#!/bin/sh
# BEGIN allostatik-state-check v0.3.14 sha256:07a3399d5819
# state-check.sh — ask git whether every repository this project lists is as a session
# should find it. Part 1's open (Start clean) and close (commit, push, confirm) run it, and
# so does the upgrade routine before it writes anything. It reads; it never writes.
#
#   sh allostatik/scripts/state-check.sh          the project holding this file
#   sh path/to/state-check.sh path/to/project      any project root
#   ALLOSTATIK_PATH_MAP='~/Projects=/mnt' sh ...   rewrite a leading path prefix, for a
#                                                  surface that mounts the folders elsewhere
#
# One line per repository — OK, DIRTY (what is off) or BLOCKED (what could not be read) —
# then exit 0 if every line is OK, 1 if any is DIRTY, else 2 if any is BLOCKED.
#
# Which repositories: the rows of "## Repositories" in allostatik/workflow.md (Part 2),
# each a path and a storage value, `remote <name>` or `local-only`. The project's own
# repository is always checked, listed or not; with no section at all it is checked as
# `remote origin`.
#
# Why these reads and not `git status` alone. Two fresh readers broke the plain reads
# thirteen ways (allostatik-dev s127). Three rules closed every break; the reads below
# are those rules applied:
#   1. A read answers by its output and exit status, never by the words of an error
#      message. Exit 0 or 1 is an answer. Exit 128 means git could not run the read
#      here, and that read is BLOCKED — never dirty, never clean.
#   2. Clean is git's own definition, read with git's hiding switched off: untracked
#      files shown, submodule changes shown, every linked worktree counted, a stash ref
#      found even without a reflog, a merge, rebase, cherry-pick, revert or bisect left
#      half done found by the files git keeps while one is.
#   3. What git was told not to see is printed, never judged: paths under
#      assume-unchanged or skip-worktree, and settings that let git trust a cache over
#      the file.
# The remote is asked itself — `ls-remote` at every URL a push would reach — so a stale
# `origin/*` cannot pass, and every local branch and tag must be there as the same object.

set -u
export GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0

case ${1:-} in
  -h|--help) sed -n '3,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac
if [ $# -gt 1 ]; then echo "usage: state-check.sh [project-root]" >&2; exit 2; fi

here=$(cd "$(dirname "$0")" && pwd) || exit 2
root=$(cd "${1:-$here/../..}" 2>/dev/null && pwd) || { echo "state-check: no such directory: ${1:-$here/../..}" >&2; exit 2; }
rootp=$(cd "$root" && pwd -P)
wf=$root/allostatik/workflow.md

tmp=$(mktemp -d) || exit 2
trap 'rm -rf "$tmp"' EXIT INT TERM HUP

# ---- the rows of "## Repositories": one line per row — the path as stated, a bar, the storage value
if [ -f "$wf" ]; then
  awk -F'|' '
    /^## Repositories/ { s = 1; next }
    /^## / { s = 0 }
    s && /^\|/ && NF >= 3 {
      p = $2; st = $3
      gsub(/^[ \t`]+|[ \t`]+$/, "", p); gsub(/^[ \t`]+|[ \t`]+$/, "", st)
      if (p == "" || p == "Repository" || p ~ /^-+$/) next
      print p "|" st
    }' "$wf" > "$tmp/rows"
else
  : > "$tmp/rows"
fi

map_from=''; map_to=''
if [ -n "${ALLOSTATIK_PATH_MAP:-}" ]; then
  map_from=${ALLOSTATIK_PATH_MAP%%=*}; map_to=${ALLOSTATIK_PATH_MAP#*=}
  case $map_from in "~"|"~/"*) map_from=$HOME${map_from#"~"} ;; esac
fi

# ---- resolve each row to a directory: directory, bar, storage value, bar, path as stated
seen_root=0
: > "$tmp/plan"
while IFS='|' read -r stated storage; do
  dir=$stated
  case $dir in
    "~"|"~/"*) dir=$HOME${dir#"~"} ;;
    /*) ;;
    ./*|../*) dir=$root/$dir ;;
    *) dir=$root ;;                      # a cell that is not a path names this project
  esac
  if [ -n "$map_from" ]; then
    case $dir in "$map_from"|"$map_from"/*) dir=$map_to${dir#"$map_from"} ;; esac
  fi
  [ "$(cd "$dir" 2>/dev/null && pwd -P)" = "$rootp" ] && seen_root=1
  printf '%s|%s|%s\n' "$dir" "$storage" "$stated" >> "$tmp/plan"
done < "$tmp/rows"
if [ $seen_root -eq 0 ]; then
  { printf '%s|%s|%s\n' "$root" "remote origin" "$root"; cat "$tmp/plan"; } > "$tmp/plan2"
  mv "$tmp/plan2" "$tmp/plan"
fi

# ---- one repository
g() {  # git in $repo: stdout to $tmp/out, first stderr line to $err, status to $rc
  git -C "$repo" "$@" >"$tmp/out" 2>"$tmp/err" </dev/null; rc=$?
  err=$(head -n 1 "$tmp/err")
}
run() {  # run LABEL GIT-ARGS... — 0 if git ran the read (rule 1), 1 if BLOCKED
  label=$1; shift
  g "$@"
  if [ "$rc" -ge 128 ]; then blocked="${blocked:+$blocked; }$label: exit $rc${err:+ ($err)}"; return 1; fi
  return 0
}
dirty_add() { dirty="${dirty:+$dirty; }$1"; }
note_add() { notes="${notes:+$notes; }$1"; }
commas() { tr '\n' ',' | sed 's/,$//; s/,/, /g'; }

check_repo() {
  dirty=''; blocked=''; notes=''; name=''
  if ! run remote remote; then verdict=BLOCKED; detail="could not read: $blocked"; return; fi
  remotes=$(cat "$tmp/out")
  listed=$(printf '%s' "$remotes" | tr '\n' ' ')

  # storage, read against git
  case $storage in
    "remote "*)
      name=${storage#remote }
      if ! printf '%s\n' "$remotes" | grep -qx -- "$name"; then
        dirty_add "declared \`remote $name\` but git remote lists ${listed:-nothing}"; name=''
      fi ;;
    local-only)
      if [ -n "$remotes" ]; then dirty_add "declared \`local-only\` but git remote lists $listed"; else note_add "local-only"; fi ;;
    *) dirty_add "storage value '$storage' is neither \`remote <name>\` nor \`local-only\`" ;;
  esac

  # clean, with hiding switched off (rule 2); what git was told not to see, printed (rule 3)
  if run status status --porcelain --untracked-files=normal --ignore-submodules=none; then
    [ -s "$tmp/out" ] && dirty_add "$(grep -c '' "$tmp/out") uncommitted path(s)"
  fi
  if run ls-files ls-files -v :/; then
    hidden=$(grep -v '^H' "$tmp/out" | cut -c3-)
    if [ -n "$hidden" ]; then
      n=$(printf '%s\n' "$hidden" | grep -c '')
      first=$(printf '%s\n' "$hidden" | head -n 5 | commas)
      [ "$n" -gt 5 ] && first="$first ..."
      note_add "$n path(s) under hide bits: $first"
    fi
  fi
  if run config config --get-regexp '^core\.(trustctime|checkstat|fsmonitor)$'; then
    [ -s "$tmp/out" ] && note_add "stat-trust settings: $(tr '\n' ';' < "$tmp/out" | sed 's/;$//; s/;/; /g')"
  fi
  if run git-dir rev-parse --git-dir; then
    gd=$(cat "$tmp/out"); case $gd in /*) ;; *) gd=$repo/$gd ;; esac
    half=''
    for f in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG rebase-apply rebase-merge sequencer; do
      [ -e "$gd/$f" ] && half="${half:+$half, }$f"
    done
    [ -n "$half" ] && dirty_add "half-done operation: $half"
  fi
  if run stash rev-parse --verify --quiet refs/stash; then
    [ "$rc" -eq 0 ] && dirty_add "a stash ref exists"
  fi
  if run worktree worktree list --porcelain; then
    n=$(awk 'BEGIN { RS = ""; n = 0 } !/(^|\n)bare(\n|$)/ { n++ } END { print n + 0 }' "$tmp/out")
    [ "$n" -ne 1 ] && dirty_add "$n non-bare worktree(s), expected 1"
  fi
  if run HEAD symbolic-ref -q HEAD; then
    if [ "$rc" -eq 1 ]; then dirty_add "HEAD is detached"
    else h=$(cat "$tmp/out"); case $h in refs/heads/*) ;; *) dirty_add "HEAD is on $h, not a branch" ;; esac
    fi
  fi

  # every local branch and tag, wherever a push would put it, as the same object
  if [ -n "$name" ]; then
    if run push-urls remote get-url --push --all "$name"; then
      cp "$tmp/out" "$tmp/urls"
      if run for-each-ref for-each-ref '--format=%(objectname) %(refname)' refs/heads refs/tags; then
        cp "$tmp/out" "$tmp/local"
        while read -r url; do
          [ -n "$url" ] || continue
          if run "ls-remote $url" ls-remote --heads --tags "$url"; then
            missing=$(awk -v R="$tmp/out" '
              FILENAME == R { if ($2 !~ /\^\{\}$/) have[$2] = $1; next }
              have[$2] != $1 { print $2 }' "$tmp/out" "$tmp/local")
            [ -n "$missing" ] && dirty_add "not at $url as the same object: $(printf '%s\n' "$missing" | sed 's#^refs/[^/]*/##' | commas)"
          fi
        done < "$tmp/urls"
      fi
    fi
  fi

  if [ -n "$dirty" ]; then verdict=DIRTY; elif [ -n "$blocked" ]; then verdict=BLOCKED; else verdict=OK; fi
  detail=$dirty
  [ -n "$blocked" ] && detail="${detail:+$detail; }could not read: $blocked"
  [ -n "$notes" ] && detail="${detail:+$detail; }$notes"
}

any_dirty=0; any_blocked=0
while IFS='|' read -r repo storage stated; do
  check_repo
  printf '%-7s %s%s\n' "$verdict" "$stated" "${detail:+: $detail}"
  case $verdict in DIRTY) any_dirty=1 ;; BLOCKED) any_blocked=1 ;; esac
done < "$tmp/plan"
[ $any_dirty -eq 1 ] && exit 1
[ $any_blocked -eq 1 ] && exit 2
exit 0
# END allostatik-state-check
