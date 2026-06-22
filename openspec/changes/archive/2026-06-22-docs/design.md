## Context

The code, container stack, sidecar, and monitoring are all in place; only the
README is still a stub. This change is documentation, so the "design" is about
structure, tone, and how to keep the docs accurate to the code rather than any
runtime architecture.

## Goals / Non-Goals

**Goals:**

- One README that takes an operator from zero to a running, git-syncing,
  optionally device-synced deployment, and tells a contributor how to build/test
  and how the upstream relationship works.
- A configuration table that is verifiably complete (every `VAULT_GITSYNC_*` the
  code reads) and correct (no invented vars).

**Non-Goals:**

- No code, behaviour, or dependency changes.
- No duplication of the sidecar bootstrap — link to `obsidian-sync/README.md`.
- No generated/site docs tooling; a single Markdown README plus the existing
  per-area files.

## Decisions

**Single README as the entry point, linking out.** Operators expect the root
README to be the map. It carries the quickstart and config inline (the things you
need at deploy time) and links to `obsidian-sync/README.md` (the sidecar
bootstrap) and `.env.example` (the annotated source of truth) rather than
restating them, so there is one place to update each fact.

**Config table derived from the code, not hand-invented.** The author cross-checks
the documented `VAULT_GITSYNC_*` set against `grep -rho 'VAULT_GITSYNC_[A-Z_]*'
src/` so the table cannot drift from or hallucinate variables. `.env.example`
already pins names/defaults; the README table mirrors it.

**Plain, concise, public.** This is public-facing copy: plain language, no
hedging, no private host or client names. Australian English spelling. The
upstream relationship is stated honestly — we consume `obsidian-web-mcp` and
contribute changes upstream (the #57 seam, the #62 write listener), with the
repin-on-merge note carried from `pyproject`.

## Risks / Trade-offs

- [Docs drift from code as later changes land] → The config section is
  grep-verifiable and the quickstart mirrors the committed compose stack, so a
  reviewer can re-check both mechanically.
- [Over-long README] → Keep deploy-time essentials inline; push detail
  (sidecar bootstrap, full env annotations) to the files that own it via links.
