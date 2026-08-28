# scripts/mutation_specs/s30_emulator_lifecycle.py
"""Mutation spec for the s30 emulator lifecycle (sequenced item 11).

    uv run python -m scripts.mutation_battery scripts/mutation_specs/s30_emulator_lifecycle.py

Scoped to the diff. The control strips the "last:" clause out of the boot
timeout -- which is observations #25 reduced to one line, since the loop that
spun forever had discarded exactly that text. If the suite tolerates a timeout
that cannot say what adb last said, nothing below means anything.

One mutation is expected to **survive**, and it is recorded rather than
removed: `check=False` -> `check=True` in `running_emulator_pids`. `pgrep`
exits 1 on no match, which is the ordinary case at open and the success case at
close, so `check=True` would raise in production every time nothing is running
-- and no offline test can see it, because the fake ignores the flag. That is
the fake-is-an-assumption gap in `docs/refs/testing-against-a-live-app.md`,
sitting in this diff where it can be pointed at.
"""

EMULATOR = "scripts/emulator.py"

CONTROL = {
    "label": "control: the timeout stops saying what adb last said (#25)",
    "file": EMULATOR,
    "old": '                f"({elapsed:.1f}s elapsed); last: {last}"',
    "new": '                f"({elapsed:.1f}s elapsed)"',
}

MUTATIONS = [
    {
        "label": "the boot predicate becomes truthiness, so `0` reads as booted",
        "file": EMULATOR,
        "old": '            if value == "1":',
        "new": "            if value:",
    },
    {
        "label": "the guard forgets it fired, so teardown can run twice",
        "file": EMULATOR,
        "old": "        self.spent = True\n        self.teardown()",
        "new": "        self.teardown()",
    },
    {
        "label": "disarm does nothing, so a successful boot tears itself down",
        "file": EMULATOR,
        "old": '        """The guarded thing succeeded -- leave the emulator up."""\n'
        "        self.spent = True",
        "new": '        """The guarded thing succeeded -- leave the emulator up."""\n'
        "        return None",
    },
    {
        "label": "the signal layer is never installed (SIGTERM leaks the emulator)",
        "file": EMULATOR,
        "old": "            set_handler(sig, handler)",
        "new": "            pass",
    },
    {
        "label": "the handler re-raises without restoring the previous disposition",
        "file": EMULATOR,
        "old": "        set_handler(signum, previous.get(signum, signal.SIG_DFL))\n"
        "        resignal(signum)",
        "new": "        resignal(signum)",
    },
    {
        "label": "boot forgets to disarm, tearing down what it just booted",
        "file": EMULATOR,
        "old": "        guard.disarm()",
        "new": "        pass",
    },
    {
        "label": "the log is appended to, so graphics errors carry across boots",
        "file": EMULATOR,
        "old": 'with log_path.open("wb") as log:',
        "new": 'with log_path.open("ab") as log:',
    },
    {
        "label": "the emulator is launched in this process group (Ctrl-C reaches it)",
        "file": EMULATOR,
        "old": "            start_new_session=True,",
        "new": "            start_new_session=False,",
    },
    {
        "label": "the boot is warm: -no-snapshot-load dropped",
        "file": EMULATOR,
        "old": '[str(binary), "-avd", avd, "-no-snapshot-load"],',
        "new": '[str(binary), "-avd", avd],',
    },
    {
        "label": "a survivor past the bound is reported as dead",
        "file": EMULATOR,
        "old": "                True, False, elapsed, survivors, "
        'f"{detail}; still up after {timeout:.0f}s"',
        "new": "                True, True, elapsed, survivors, "
        'f"{detail}; still up after {timeout:.0f}s"',
    },
    {
        "label": "boot stops refusing to start on top of a running emulator",
        "file": EMULATOR,
        "old": "    already = running_emulator_pids(run=run)",
        "new": "    already = ()",
    },
    {
        "label": "pgrep's no-match exit becomes an error (production-only; fake ignores it)",
        "file": EMULATOR,
        "old": 'result = run(["pgrep", "-f", QEMU_PATTERN], capture_output=True, '
        "text=True, check=False)",
        "new": 'result = run(["pgrep", "-f", QEMU_PATTERN], capture_output=True, '
        "text=True, check=True)",
        "expect": "survive",
    },
]
