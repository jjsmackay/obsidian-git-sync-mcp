# Design

## Context

The behaviour documented here already ships and is verified on disk:
`obsidian-sync/entrypoint.sh`, `obsidian-sync/Dockerfile`, `docker-compose.yml`,
and `README.md`. This change adds no code; it records the shipped behaviour as
spec deltas, mirroring `2026-06-28-git-repo-bootstrap`.

## Decisions

- **Bootstrap is explicit-only — never auto-run.** The entry point runs bootstrap
  only on an explicit `bootstrap` arg or `BOOTSTRAP` env. It deliberately does not
  auto-start bootstrap on a detected TTY: compose's `tty: true` makes stdin a TTY
  even with nobody attached, so auto-on-TTY would hang forever at the `ob login`
  prompt. The poll loop auto-starts only *sync*, never bootstrap.
- **Passthrough escape hatch.** Any explicit command that is not `bootstrap` is
  exec'd verbatim (e.g. `docker run … <image> sh`), so an operator is never
  second-guessed.
- **Image pre-creates the config dir as uid 10001.** Docker copies an existing
  mount-target dir's ownership into a fresh named volume on first use, so creating
  `/home/ob/.config/obsidian-headless` as `ob` before the mount makes the volume
  inherit `ob` ownership — no host-side chown for the sidecar's `config` volume.
- **The vault named volume has no such fix.** A fresh named vault volume mounts
  root-owned; it must be seeded and `chown -R 10001:10001`'d so the uid-10001
  container user can commit. Documented in the README, not solved in an image.

## Scope / risk

Spec/docs only — no Python logic change, so no test change (124 tests unaffected).

## Out of scope

- The idle→auto-start poll and `bootstrap --reset`: already spec'd by earlier
  changes; not restated here.
- Any change to the entry point, image, compose, or README.
- An image-side fix for the vault volume's root ownership (the README documents
  the manual seed + chown instead).
