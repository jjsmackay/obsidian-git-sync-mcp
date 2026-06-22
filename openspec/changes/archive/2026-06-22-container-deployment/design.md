## Context

The package installs and tests green but has no runtime packaging. Upstream
publishes no container image and ships launchd plists for a macOS host, so there
is no base image to extend — we build from `python:3.12-slim`. Our `pyproject`
already pulls the upstream server (via the `feat/write-listener` git branch) and
`ruamel.yaml`, so installing this package into the image brings the whole runtime.

## Goals / Non-Goals

**Goals:**

- A small image that runs `serve([GitSyncExtension()])` via our entry point, with
  `git` present for the worker.
- A Compose `mcp` service that is operable: env-driven, vault mounted, one port,
  restart policy, healthcheck.
- One `.env.example` that is the authoritative configuration contract and
  finalises the `VAULT_GITSYNC_*` names.

**Non-Goals:**

- The `obsidian-sync` sidecar (next change) — only the profile seam is left open.
- The outbound push heartbeat (monitoring change).
- Any baked-in tunnel/proxy. Only the MCP port is published; remote exposure is
  documented.
- Baking credentials into the image.

## Decisions

**`FROM python:3.12-slim` + `git`, install with uv `--system`.** No upstream image
exists, and the slim base keeps the image small. `git` and `ca-certificates` are
apt-installed because (a) the build resolves the upstream git dependency and (b)
the worker shells out to `git` at runtime. uv with `--system` matches the
workspace Dockerfile convention and resolves the git + PyPI deps in one step.

**TCP healthcheck, not HTTP `/health`.** `/health` is in the upstream auth-exempt
set but has no handler (it 404s), and the MCP transport at `/` speaks a handshake,
not a plain GET — neither is a clean liveness signal. A dependency-free Python
one-liner that opens a TCP connection to the MCP port confirms the server is up
and listening, which is what a container healthcheck needs. Richer
liveness/monitoring (the outbound push heartbeat) is the monitoring change.

**Only publish the MCP port; bind inside the container network otherwise.** The
upstream server defaults to binding loopback for safety; in a container it must
bind `0.0.0.0` to be reachable on the published port, so `.env.example` sets
`VAULT_MCP_HOST=0.0.0.0` and documents that the port should sit behind a reverse
proxy / tunnel for remote access. We publish nothing else.

**`.env.example` is the configuration contract.** It lists the upstream `VAULT_*`
vars the deployment needs (path, token, port, host, allowed hosts, public URL,
OAuth) and every `VAULT_GITSYNC_*` var, with the extension disabled by default so
a copy-and-run is a safe no-op. This is where the provisional names are pinned to
exactly what the code reads.

**Vault + credentials are mounted, never baked.** The vault git working tree is a
bind/volume mount at `VAULT_PATH`. Pushing needs a credential; `.env.example` and
the compose comments document mounting a deploy key (read-only) or using a
token-bearing remote URL, kept out of the image and out of git.

## Risks / Trade-offs

- [Building installs from a git branch (`feat/write-listener`), not a release] →
  Tracked already in `pyproject` with a repin TODO for when #62 merges; the image
  inherits that pin. Documented.
- [`0.0.0.0` bind is unauthenticated network exposure if the port is published
  without a proxy] → The server still enforces bearer auth; `.env.example` and
  docs stress publishing only behind a tunnel/proxy and setting
  `VAULT_MCP_ALLOWED_HOSTS` / `VAULT_MCP_PUBLIC_URL`.
- [A TCP healthcheck reports "listening" even if the app is mis-wired behind the
  socket] → Acceptable for a liveness check; readiness/correctness is covered by
  the monitoring heartbeat and the startup fail-closed validation.
