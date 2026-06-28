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
# Install the entry point + bootstrap scripts (root-owned, executable) before
# dropping privileges. The entry point decides whether to sync, bootstrap, or
# idle-and-instruct; `bootstrap` is the interactive one-time setup. See each
# script's header and obsidian-sync/README.md.
COPY --chmod=0755 entrypoint.sh /usr/local/bin/entrypoint
COPY --chmod=0755 bootstrap.sh /usr/local/bin/bootstrap

RUN useradd --create-home --uid 10001 ob
ENV HOME=/home/ob
USER ob
WORKDIR /home/ob

# Pre-create the config dir (as `ob`, so it is owned by uid 10001) BEFORE the
# named volume is mounted here. Docker copies an existing mount-target dir's
# ownership into a fresh named volume on first use; without this the volume
# mounts root-owned and `ob` cannot write its credentials/state. Creating it
# here makes the volume inherit `ob` ownership -- no host-side chown needed.
RUN mkdir -p /home/ob/.config/obsidian-headless

# Healthcheck doubles as a "bootstrapped?" signal: the config dir is non-empty
# only after login/sync-setup, so an un-bootstrapped sidecar reports unhealthy
# in `docker ps` / Komodo instead of looking fine while idle.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD [ -n "$(ls -A /home/ob/.config/obsidian-headless 2>/dev/null)" ]

# The entry point owns the run decision (sync / bootstrap / idle); no CMD needed.
# Until a one-time `bootstrap` (ob login + sync-setup) has populated the config
# volume, a headless `up -d` start idles with instructions rather than looping.
ENTRYPOINT ["entrypoint"]
