# Obsidian Headless Sync sidecar.
#
# Runs the official `obsidian-headless` CLI (`ob`) headless, beside the mcp
# service, so Obsidian Sync keeps human devices (phone, desktop) in step while
# the headless host serves MCP and commits the working tree to git.
#
# `obsidian-headless` is an npm package (bin `ob` -> cli.js) with a native
# `better-sqlite3` dependency. We pin the version for reproducible builds.
FROM node:22-bookworm-slim

# Install obsidian-headless globally, pinned.
#
# better-sqlite3 path: PREBUILT. On node:22-bookworm-slim the install resolves a
# prebuilt better-sqlite3 binary via prebuild-install -- NO build toolchain is
# required. If a future version/base lacks a prebuilt binary, the install will
# fall back to compiling from source and fail for want of a compiler; in that
# case add the toolchain before the npm install, e.g.:
#
#   RUN apt-get update \
#       && apt-get install -y --no-install-recommends python3 make g++ \
#       && rm -rf /var/lib/apt/lists/*
#
# Confirmed at build time (obsidian-headless@0.0.12): the prebuilt path works, so
# the toolchain is intentionally omitted to keep the image slim.
RUN npm install -g obsidian-headless@0.0.12 \
    && npm cache clean --force

# Run as a non-root user with a stable HOME so `ob` writes its config + sync
# state to a known, mountable path. On Linux `ob` uses
# $XDG_CONFIG_HOME || $HOME/.config, then ".../obsidian-headless" -- so with
# HOME=/home/ob the config dir is /home/ob/.config/obsidian-headless
# (credentials + per-vault state.db live there). The compose file mounts a named
# volume at exactly that path.
RUN useradd --create-home --uid 10001 ob
ENV HOME=/home/ob
USER ob
WORKDIR /home/ob

# Default command: long-running continuous sync of the shared vault working tree.
# `ob sync --path <vault> --continuous` watches the vault and keeps it in step
# with the remote. The vault path is the container mount point (VAULT_PATH,
# default /vault); the compose service overrides this command with the resolved
# path. Until a one-time `ob login` + `ob sync-setup` has populated the config
# volume (see README), this exits early reporting "No account logged in".
CMD ["ob", "sync", "--path", "/vault", "--continuous"]
