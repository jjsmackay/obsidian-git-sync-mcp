#!/usr/bin/env bash
# setup.sh — Bootstrap the Obsidian LXC (Debian 13 Trixie)
#
# Run as root. Re-running is safe; each step is idempotent.
#
# Usage:
#   sudo bash /home/obsidian/obsidian-sync/scripts/setup.sh

set -euo pipefail

MCP_USER="obsidian"
MCP_HOME="/home/${MCP_USER}"
MCP_PROJECT="${MCP_HOME}/obsidian-web-mcp"
SYNC_PROJECT="${MCP_HOME}/obsidian-sync"
VAULT_DIR="${MCP_HOME}/Vaults/a self-hosted homelab (Sync)"
MCP_ENV_DIR="${MCP_HOME}/.config/obsidian-mcp"
SYNC_ENV_DIR="${MCP_HOME}/.config/obsidian-sync"

info()    { echo "[INFO]  $*"; }
ok()      { echo "[OK]    $*"; }
warn()    { echo "[WARN]  $*"; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "[ERROR] Run as root (or with sudo)." >&2
        exit 1
    fi
}

require_root
info "Starting Obsidian LXC setup"

# --- System packages ---
apt-get update -qq
for pkg in ripgrep git curl; do
    if ! command -v "$pkg" &>/dev/null 2>&1; then
        info "Installing $pkg..."
        apt-get install -y -qq "$pkg"
    fi
done
ok "System packages ready"

# --- uv ---
UV_BIN="${MCP_HOME}/.local/bin/uv"
if [[ ! -x "$UV_BIN" ]]; then
    info "Installing uv..."
    sudo -u "$MCP_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
ok "uv: $(sudo -u "$MCP_USER" "$UV_BIN" --version)"

# --- Clone/update repos ---
for repo_url in \
    "https://github.com/${MCP_REPO}.git:${MCP_PROJECT}" \
    "https://github.com/${PROJECT_REPO}.git:${SYNC_PROJECT}"; do
    url="${repo_url%%:*}"
    dir="${repo_url#*:}"
    if [[ ! -d "$dir/.git" ]]; then
        info "Cloning $url..."
        sudo -u "$MCP_USER" git clone "$url" "$dir"
    else
        info "Updating $dir..."
        sudo -u "$MCP_USER" git -C "$dir" pull --ff-only
    fi
done
ok "Repos ready"

# --- Git identity for vault ---
if [[ -d "${VAULT_DIR}/.git" ]]; then
    sudo -u "$MCP_USER" git -C "$VAULT_DIR" config user.name "Bobsidian"
    sudo -u "$MCP_USER" git -C "$VAULT_DIR" config user.email "${GIT_AUTHOR_EMAIL}"
    ok "Vault git identity set"
else
    warn "Vault is not a git repo — set git identity manually after init"
fi

# --- Env files ---
for env_pair in \
    "${MCP_ENV_DIR}:${SYNC_PROJECT}/env/obsidian-mcp.env.example" \
    "${SYNC_ENV_DIR}:${SYNC_PROJECT}/env/obsidian-sync.env.example"; do
    env_dir="${env_pair%%:*}"
    template="${env_pair#*:}"
    env_file="${env_dir}/env"
    sudo -u "$MCP_USER" mkdir -p "$env_dir"
    chmod 700 "$env_dir"
    if [[ ! -f "$env_file" ]]; then
        sudo -u "$MCP_USER" cp "$template" "$env_file"
        chmod 600 "$env_file"
        warn "Created $env_file from template — edit and fill in secrets"
    else
        ok "$env_file already exists"
    fi
done

# --- Systemd units ---
cp "${SYNC_PROJECT}/systemd/obsidian-headless-sync.service" /etc/systemd/system/
mkdir -p /etc/systemd/system/obsidian-headless-sync.service.d
cp "${SYNC_PROJECT}/systemd/obsidian-headless-sync.service.d/override.conf" \
    /etc/systemd/system/obsidian-headless-sync.service.d/
cp "${SYNC_PROJECT}/systemd/obsidian-git-sync.service" /etc/systemd/system/
cp "${SYNC_PROJECT}/systemd/obsidian-git-sync.timer" /etc/systemd/system/
cp "${SYNC_PROJECT}/systemd/obsidian-mcp.service" /etc/systemd/system/
systemctl daemon-reload
ok "Systemd units installed"

for svc in obsidian-headless-sync obsidian-mcp; do
    systemctl enable "$svc"
done
systemctl enable obsidian-git-sync.timer
ok "Services enabled"

# --- Cron: headless heartbeat ---
CRON_LINE="* * * * * ${SYNC_PROJECT}/scripts/obsidian-headless-heartbeat.sh"
if ! sudo -u "$MCP_USER" crontab -l 2>/dev/null | grep -qF "obsidian-headless-heartbeat"; then
    (sudo -u "$MCP_USER" crontab -l 2>/dev/null; echo "$CRON_LINE") | sudo -u "$MCP_USER" crontab -
    ok "Cron job installed for headless heartbeat"
else
    ok "Headless heartbeat cron already exists"
fi

# --- Pre-warm MCP venv ---
info "Syncing MCP Python deps..."
sudo -u "$MCP_USER" bash -c "cd '${MCP_PROJECT}' && '${UV_BIN}' sync"
ok "Python deps ready"

echo ""
echo "========================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Edit ${MCP_ENV_DIR}/env (TOKEN, CLIENT_SECRET, ALLOWED_HOSTS)"
echo "    2. Edit ${SYNC_ENV_DIR}/env (heartbeat URLs)"
echo "    3. systemctl start obsidian-headless-sync"
echo "    4. systemctl start obsidian-git-sync.timer"
echo "    5. systemctl start obsidian-mcp"
echo "    6. journalctl -u obsidian-mcp -f"
echo "========================================================"
