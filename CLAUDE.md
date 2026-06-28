# CLAUDE.md

Operational notes for this repo. Project thesis, tech stack, and deployment
live in `openspec/config.yaml` (context block) and `README.md` — don't duplicate
them here.

## Commands
- Test: `uv run --extra dev python -m pytest`  (bare `pytest` / `uv run pytest` fail — needs the dev extra + `python -m`)
- The two images build via `.github/workflows/build-containers.yml` on push to
  `main`/`v*` tags → `ghcr.io/jjsmackay/obsidian-mcp` and `…/obsidian-sync`.

## Change workflow
- Spec-driven via **OpenSpec**: propose changes with `/opsx:propose`, not ad-hoc edits.
- `.claude/` is gitignored; regenerate slash commands with `openspec init --tools claude`.

## Gotchas
- `VAULT_GIT_ENABLED=true` makes the mcp container **fail-closed at startup** if
  the vault isn't a git working tree or the remote is missing (`config.py:validate_gitsync`).
- `obsidian-web-mcp` is consumed as base image + Python dependency; contribute
  changes **upstream**, don't fork.
