## Context

The MCP container serves the vault and commits to git; this sidecar runs the
official `obsidian-headless` CLI (`ob`) so Obsidian Sync keeps human devices in
step. `obsidian-headless` is an npm package (bin `ob`, deps `better-sqlite3` +
`commander`); state lives under `~/.config/obsidian-headless/sync/<vault-id>/`
(`state.db`, `sync.log`). Prior art: `crosbyh/obsidian-headless-sync-docker`.

The HANDOFF marks this the biggest standalone risk — `better-sqlite3` is a native
module and `ob` must run with no display — so it is isolated in its own change
and its own image, leaving the `mcp` service untouched.

## Goals / Non-Goals

**Goals:**

- A sidecar image where `ob` builds and runs headless.
- An opt-in (`obsidian` profile) Compose service that shares the vault and
  persists `ob` state on a named volume.
- A bootstrap procedure grounded in the CLI's real subcommands.

**Non-Goals:**

- Automating Obsidian Sync login — it needs a real account/credentials; it is an
  operator step, documented.
- Reading `state.db` for `user@device` attribution (v2).
- Any change to the `mcp` service or the extension code.

## Decisions

**Separate Node image, not multi-purpose with the mcp image.** The mcp image is
Python; `ob` is Node + a native sqlite module. Keeping them separate avoids
bloating the always-on mcp image with a Node toolchain and isolates the risky
build. The two share only the vault volume.

**Pin `obsidian-headless` and satisfy `better-sqlite3` deterministically.** Pin
the version (`0.0.12` at time of writing) so the build is reproducible. Prefer a
Node base that lets `better-sqlite3` use a prebuilt binary; fall back to adding
`python3`/`make`/`g++` only if the prebuild is unavailable for the base — decided
at implementation time by what actually builds, and recorded.

**Opt-in via the `obsidian` profile.** Not everyone wants Obsidian Sync (git-only
is a valid deployment). A Compose profile makes the sidecar explicit opt-in
without a second compose file, and keeps `docker compose up` minimal.

**Persisted named volume for `ob` state; shared vault mount.** Credentials and
`state.db` must survive restarts, so they live on a named volume, not the
container layer. The vault is the same working tree the mcp service mounts, so a
device edit synced down by `ob` lands on disk and the git-sync worker's timer
sweep commits it as `sync:`.

**Bootstrap grounded in the real CLI.** Rather than guess subcommands, the
implementation runs `ob --help` in the built image and writes the bootstrap
(login + sync-setup) and the long-running service command from the actual output.

## Risks / Trade-offs

- [`better-sqlite3` may not have a prebuilt binary for the chosen base → build
  fails] → Add the build toolchain (`python3`, `make`, `g++`) to the image if the
  prebuild is missing; record which path was needed.
- [Cannot validate real sync without an Obsidian account] → Scope validation to
  "image builds + `ob` runs headless + profile gating + volume wiring"; the login
  is a documented operator step. State this boundary plainly.
- [Two writers on one tree (ob writing device edits, the worker staging/committing)
  could race] → The worker's `git add -A` is self-healing: a partially-synced file
  is recommitted on the next sweep. Documented in the git-worker design.
- [`ob` config path assumption] → Confirm the actual config dir from the running
  CLI before pinning the volume mount path.
