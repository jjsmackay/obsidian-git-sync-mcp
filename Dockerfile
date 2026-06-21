# Runs the upstream obsidian-web-mcp server with our GitSyncExtension loaded.
# Upstream publishes no image, so we build from the Python slim base.
FROM python:3.12-slim

# git: the sync worker shells out to it at runtime, and the build resolves the
#      upstream server dependency (a git+https reference until PR #62 merges).
# ca-certificates: TLS trust for the git fetch over https.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv matches the workspace tooling convention; install into the system env.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy the project source (respecting .dockerignore) and install it. This pulls
# the upstream obsidian-web-mcp (from its git branch) and ruamel.yaml.
COPY . .
RUN uv pip install --system .

# Drop root: nothing here needs it, and the vault is a mounted volume.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# The MCP transport port (upstream default 8420; overridable via VAULT_MCP_PORT).
EXPOSE 8420

# Liveness: a dependency-free TCP connect to the MCP port. python is in the base
# image, so no curl/wget is required. Exit 0 when the socket accepts a connection.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,socket,sys; s=socket.socket(); s.settimeout(3); sys.exit(0 if s.connect_ex(('127.0.0.1', int(os.environ.get('VAULT_MCP_PORT','8420'))))==0 else 1)"]

# Our entry point: builds GitSyncExtension(), validates fail-closed, runs serve([ext]).
CMD ["obsidian-git-sync-mcp"]
