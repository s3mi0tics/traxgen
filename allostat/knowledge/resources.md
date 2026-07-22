# traxgen — Resources

External references for this project — docs, repos, and sites Claude pulls in when relevant. Local reference copies live in the repo at `docs/refs/`, indexed by `docs/refs/README.md` — that folder is the project's committed Layer-3 corpus and is NOT duplicated here.

**Last updated:** 2026-07-22

## References

```yaml
- name: allostat
  description: the methodology this project's configuration is built on; reach for it when revisiting how the setup is structured or extending it
  location: "https://github.com/allostat/allostat"

- name: lfrancke/murmelbahn
  description: the reverse-engineered GraviTrax course format — Rust source is schema ground truth (lib/src/app/layer.rs; imhex-schema.txt mirrors it); reach for it on any binary format question. Apache-2.0 — attribution required
  location: "https://github.com/lfrancke/murmelbahn"

- name: murmelbahn course API
  description: fetches any shared course's raw bytes by share code — the oracle-fixture pipeline; reach for it when acquiring fixtures or app-built ground truth
  location: "https://murmelbahn.fly.dev/api/course/{code}/raw"

- name: GraviTrax Fandom wiki
  description: piece data of last resort — known wrong on long-rail Δheight; source priority is physical inspection > wiki > Ravensburger listings
  location: "https://gravitrax.fandom.com"

- name: Cross 2016 (AAPT)
  description: velocity-dependent rolling-resistance form, if Phase 2 physics ever needs more than textbook μ_r
  location: cited in the archived docs/PLAN.md, Phase 2 preview
```
