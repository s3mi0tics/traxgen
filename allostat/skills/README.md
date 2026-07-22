# Skills — traxgen

Layer-4 skills for this project. Each skill is a folder with a `SKILL.md` inside — a reference note Claude reads when working here: what a tool or capability is, how it's set up, how it behaves, and when to use it. Skills are *what Claude can do and how it works with your tools*, distinct from *what Claude knows* (Layer 3, `../knowledge/`) and *which surface Claude runs on* (Layer 5).

This folder ships empty — you write your own skills.

## Layout

- **`standard/`** — tools with public docs elsewhere (Anthropic, third-party). The `SKILL.md` documents *your* project-specific use — scope configured, quirks, surface coverage — not the tool itself.
- **`custom/`** — capabilities with no public docs (your own scripts, aliases, commands). Here the `SKILL.md` *is* the canonical documentation.

Each skill lives in its own folder with a `SKILL.md` inside (e.g. `standard/my-tool/SKILL.md`). For the header fields, the folder-loading vs. Anthropic auto-discovery model, and the full format, see the skills-layer doc in allostat (`skills/README.md`) — that's the canonical explanation, not duplicated here.

## Adding a skill

1. Create a folder under `standard/` or `custom/` named for the skill (e.g. `standard/my-tool/`).
2. Copy `allostat/templates/skill_template.md` into it as `SKILL.md`; fill in the header and body.
3. Add a one-line entry to the index below — the directory listing is the index.
4. Leave `discovery` at `methodology-folder` unless the skill genuinely needs Anthropic auto-discovery.

## Index

### Standard

*(none yet)*

### Custom

*(none yet — the first custom skill creates `custom/` and adds an entry here.)*
