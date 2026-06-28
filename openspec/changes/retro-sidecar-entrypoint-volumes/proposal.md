## Why

Three pieces of the obsidian-sync sidecar shipped without an OpenSpec change, so
the specs do not record them:

- The sidecar **entry-point dispatch** logic (commits `409f084` + `2872c79`):
  explicit `bootstrap` / `BOOTSTRAP` runs bootstrap; any other explicit command
  is exec'd verbatim (a passthrough escape hatch); no command falls through to a
  four-way start decision. Two later changes spec'd the idle→auto-start poll and
  `bootstrap --reset`, but they build on this base dispatch behaviour that was
  never itself written down.
- The sidecar image **pre-creates the `ob` config dir as uid 10001** before the
  named `config` volume mounts, so a fresh volume inherits `ob` ownership and no
  host-side chown is needed for the sidecar.
- The README's **vault named-volume ownership gotcha** (a fresh named vault
  volume mounts root-owned, so it must be seeded and `chown -R 10001:10001`'d) and
  the **commit-identity / bootstrap-ordering / re-bootstrap** documentation folded
  in by `661fedf`.

This is a bookkeeping change: the behaviour is already on disk and in production.
We are recording it for spec fidelity, exactly as `2026-06-28-git-repo-bootstrap`
did for the Dockerfile/compose/README git-bootstrap work.

## What Changes

- **Spec only — no code, Dockerfile, compose, shell, or README edits.** The
  current files already reflect the shipped behaviour; this change documents them.
- Record the entry-point dispatch contract as a requirement (explicit-only
  bootstrap, passthrough escape hatch, four-way start decision). Do **not** restate
  the already-spec'd idle auto-start or `--reset` requirements.
- Record the `config` named-volume ownership behaviour (image pre-creates the dir
  as uid 10001 so a fresh volume inherits `ob` ownership).
- Record the vault named-volume ownership gotcha and the commit-identity /
  ordering / re-bootstrap docs.

## Capabilities

### Modified Capabilities
- `obsidian-sync-sidecar`: documents the entry-point dispatch contract and the
  `config` named-volume ownership behaviour (pre-created dir → inherited ownership).
- `container-deployment`: documents that a fresh named vault volume mounts
  root-owned and must be seeded + `chown -R 10001:10001`'d for the uid-10001
  container user to commit.
- `docs`: documents the worker commit identity, the bootstrap ordering between the
  git tree and the `ob` bootstrap, and the sidecar re-bootstrap (`--reset`) path.

### New Capabilities
<!-- None. This records already-shipped behaviour for existing capabilities. -->

## Impact

- Files: spec deltas only (`obsidian-sync-sidecar`, `container-deployment`, `docs`).
- No Python logic change; no test change (124 tests unaffected).
- Operational: none — the behaviour already ships. This closes a spec-fidelity gap.
