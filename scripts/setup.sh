#!/usr/bin/env bash
# setup.sh — Bootstrap the Obsidian LXC (Debian 13 Trixie)
#
# Run as root. Re-running is safe; each step is idempotent.
#
# Usage:
#   sudo bash /home/bobsidian/obsidian-sync/scripts/setup.sh

set -euo pipefail

USER="bobsidian"
HOME_DIR="/home/${USER}"
MCP_DIR="${HOME_DIR}/obsidian-mcp"
SYNC_DIR="${HOME_DIR}/obsidian-sync"
VAULT_DIR="${HOME_DIR}/obsidian-vault"
MCP_ENV_DIR="${HOME_DIR}/.config/obsidian-mcp"
SYNC_ENV_DIR="${HOME_DIR}/.config/obsidian-sync"

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
info "Starting Bobsidian setup"

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
UV_BIN="${HOME_DIR}/.local/bin/uv"
if [[ ! -x "$UV_BIN" ]]; then
    info "Installing uv..."
    sudo -u "$USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
ok "uv: $(sudo -u "$USER" "$UV_BIN" --version)"

# --- Clone/update repos ---
for repo_url in \
    "https://github.com/${MCP_REPO}.git|${MCP_DIR}" \
    "https://github.com/${PROJECT_REPO}.git|${SYNC_DIR}"; do
    url="${repo_url%%|*}"
    dir="${repo_url#*|}"
    if [[ ! -d "$dir/.git" ]]; then
        info "Cloning $url..."
        sudo -u "$USER" git clone "$url" "$dir"
    else
        info "Updating $dir..."
        sudo -u "$USER" git -C "$dir" pull --ff-only
    fi
done
ok "Repos ready"

# --- Git identity for vault ---
if [[ -d "${VAULT_DIR}/.git" ]]; then
    sudo -u "$USER" git -C "$VAULT_DIR" config user.name "bobsidian"
    sudo -u "$USER" git -C "$VAULT_DIR" config user.email "${GIT_AUTHOR_EMAIL}"
    ok "Vault git identity set"
else
    warn "Vault is not a git repo — set git identity manually after init"
fi

# --- Env files ---
for env_pair in \
    "${MCP_ENV_DIR}:${SYNC_DIR}/env/obsidian-mcp.env.example" \
    "${SYNC_ENV_DIR}:${SYNC_DIR}/env/obsidian-sync.env.example"; do
    env_dir="${env_pair%%:*}"
    template="${env_pair#*:}"
    env_file="${env_dir}/env"
    sudo -u "$USER" mkdir -p "$env_dir"
    chmod 700 "$env_dir"
    if [[ ! -f "$env_file" ]]; then
        sudo -u "$USER" cp "$template" "$env_file"
        chmod 600 "$env_file"
        warn "Created $env_file from template — edit and fill in secrets"
    else
        ok "$env_file already exists"
    fi
done

# --- Systemd units ---
cp "${SYNC_DIR}/systemd/obsidian-sync.service" /etc/systemd/system/
cp "${SYNC_DIR}/systemd/obsidian-git.service" /etc/systemd/system/
cp "${SYNC_DIR}/systemd/obsidian-git.timer" /etc/systemd/system/
cp "${SYNC_DIR}/systemd/obsidian-mcp.service" /etc/systemd/system/
systemctl daemon-reload
ok "Systemd units installed"

for svc in obsidian-sync obsidian-mcp; do
    systemctl enable "$svc"
done
systemctl enable obsidian-git.timer
ok "Services enabled"

# --- Cron: headless heartbeat ---
CRON_LINE="* * * * * ${SYNC_DIR}/scripts/heartbeat.sh"
if ! sudo -u "$USER" crontab -l 2>/dev/null | grep -qF "scripts/heartbeat.sh"; then
    (sudo -u "$USER" crontab -l 2>/dev/null; echo "$CRON_LINE") | sudo -u "$USER" crontab -
    ok "Cron job installed for headless heartbeat"
else
    ok "Headless heartbeat cron already exists"
fi

# --- Pre-warm MCP venv ---
info "Syncing MCP Python deps..."
sudo -u "$USER" bash -c "cd '${MCP_DIR}' && '${UV_BIN}' sync"
ok "Python deps ready"

# --- Pre-warm frontmatter stamper (PEP 723 inline deps) ---
info "Pre-warming frontmatter stamper..."
sudo -u "$USER" "${UV_BIN}" run --script "${SYNC_DIR}/scripts/stamp-frontmatter.py" >/dev/null 2>&1 || true
ok "Frontmatter stamper ready"

echo ""
echo "========================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Edit ${MCP_ENV_DIR}/env (TOKEN, CLIENT_SECRET, ALLOWED_HOSTS)"
echo "    2. Edit ${SYNC_ENV_DIR}/env (heartbeat URLs)"
echo "    3. systemctl start obsidian-sync"
echo "    4. systemctl start obsidian-git.timer"
echo "    5. systemctl start obsidian-mcp"
echo "    6. journalctl -u obsidian-mcp -f"
echo "========================================================"
