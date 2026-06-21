# obsidian-git-sync-mcp

A dockerised, self-hostable host that runs an Obsidian vault headlessly and serves it to MCP clients, with pluggable sync.

Git sync runs as an in-process extension to [obsidian-web-mcp](https://github.com/jimprosser/obsidian-web-mcp) (via its extension seam): the vault stays available to AI assistants over MCP, git mirrors history as a backup and audit trail, and Obsidian Sync (optional) keeps devices in step.

Status: early development. Design and change proposals live under `openspec/` (spec-driven via [OpenSpec](https://github.com/Fission-AI/OpenSpec)).

## Licence

MIT — see [LICENSE](LICENSE).
