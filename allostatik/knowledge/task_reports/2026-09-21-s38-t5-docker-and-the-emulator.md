# s38-t5 — can the work run inside a Docker container?

**Status:** STOPPED — needs Colby: how should the container reach the emulator? (1) a drop folder that a script on the Mac watches, running a copy of traxgen only he updates; (2) SSH with one allowed command; (3) no Docker, Claude Code in its built-in macOS sandbox instead. The pick is (1).

**In one paragraph:** the Android emulator can't run inside Docker on this Mac. On a Mac, Docker runs inside a Linux virtual machine, and the emulator needs to start a virtual machine of its own inside that one. The M1 chip can't do that (Apple added it on M3). Without it, the emulator runs everything in software, which is slower still than the software drawing that broke renders in s35. So Claude Code can live in a container for editing, tests, reports and commits, but renders have to run on the Mac itself, reached through a narrow door. Which door is Colby's call, because it decides what code may run on his Mac.

## Open

This open half was written after the research, which ran before the task routine existed. It is recorded here so that the finding lives in a record rather than a conversation (s38-t4, finding 2).

- **Goal:** find out whether traxgen's autonomous work can run inside a Docker container on Colby's Mac, as he asked, and what that means for renders.
- **Scope:** this report only. No code.
- **Budget:** 15 minutes of reading.
- **Done check:**
  1. *Step:* the research.
  2. *True after:* the report names whether the Android emulator can run in Docker on this Mac, with sources, and the options that follow.
  3. *Miss case:* a conclusion with no source a reader can open.
  4. *Reads:* the sources linked below, which existed before this task.
  5. *Check:* each claim in the close carries a link, and the chip in question is the one the device reported in s37 (`Apple M1 Pro`).
- **Outcomes declared before any live run:** none, because there is no live run.

## Close

- **What happened:** read the sources below, and asked a guide agent for Claude Code's documented sandbox, dev-container and permission settings.
- **Findings, each with its source:**
  - Docker Desktop cannot give a container nested virtualization: [docker/desktop-feedback#314](https://github.com/docker/desktop-feedback/issues/314). The Android emulator in Docker needs KVM, which needs nested virtualization: [Docker forum](https://forums.docker.com/t/is-it-possible-to-run-android-emulator-on-docker-with-kvm-nested-virtualization/7038). Apple silicon gained nested virtualization with M3: [Apple Community](https://discussions.apple.com/thread/255314811). The device reported `Apple M1 Pro` in s37's boot grade.
  - Claude Code has a built-in sandbox (Seatbelt on macOS) that limits writes and network, with `sandbox.excludedCommands` for commands that must run outside it: [sandboxing](https://code.claude.com/docs/en/sandboxing.md). Anthropic's reference dev container (`.devcontainer/` with a firewall script) is the documented place for unattended runs with permission prompts off: [dev containers](https://code.claude.com/docs/en/devcontainer.md).
- **The options that follow:**
  1. *A drop folder.* The container writes a request (a share code) into a shared folder. A script on the Mac, running from a separate copy of traxgen that only Colby updates, renders it and writes the result back. Only data crosses, so harness changes run live only after he updates that copy.
  2. *SSH with one allowed command.* The same idea over a network connection. It needs Remote Login and a key.
  3. *No Docker.* Claude Code on the Mac in its sandbox. The render step must run outside the sandbox, so code the agent just edited would run on the Mac unchecked.
- **What changed:** this report and the ledger. The commit is the one that adds this report's close.
- **Evidence:** `task_check s38-t5` (the next line in the ledger's story); the links above.
- **Decisions made inside the task:** none. The door is Colby's decision, because it sets what code may run on his Mac (stop reason 2, since it shapes the goal he gave: "I want to do it inside of a docker container").
- **For the record:**
  - `plan.md`: s39 opens with this decision, then builds the container and the door, then the live proof s38-t2 stopped on.
  - `knowledge/environment.md`: the emulator can't run in Docker on the M1; the reasons and links are above.
- **Friction:** the routine has no form for a research task that changes no files. An empty `scope=` worked, and `task_check` held it to the report alone.
- **Next:** Colby's answer on the door.
