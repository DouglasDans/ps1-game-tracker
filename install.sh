#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
SERVICE_NAME="ps1-tracker"
CURRENT_USER="$(whoami)"

# ── helpers ────────────────────────────────────────────────────────────────────
ok()   { echo "[OK] $*"; }
info() { echo "     $*"; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

# ── python version ─────────────────────────────────────────────────────────────
check_python() {
    local ver
    ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local major minor
    IFS='.' read -r major minor <<< "$ver"
    if [[ "$major" -lt 3 ]] || [[ "$major" -eq 3 && "$minor" -lt 11 ]]; then
        fail "Python 3.11+ required (found $ver)"
    fi
    ok "Python $ver"
}

# ── virtualenv + deps ──────────────────────────────────────────────────────────
setup_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        info "Creating virtualenv at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
    fi
    info "Installing dependencies..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
    ok "Dependencies installed"
}

# ── config ─────────────────────────────────────────────────────────────────────
setup_config() {
    if [[ ! -f "$SCRIPT_DIR/config.toml" ]]; then
        cp "$SCRIPT_DIR/config.toml.example" "$SCRIPT_DIR/config.toml"
        ok "config.toml created from example"
        info "Edit $SCRIPT_DIR/config.toml before starting the service"
    else
        ok "config.toml already exists"
    fi
}

# ── data directory ─────────────────────────────────────────────────────────────
setup_data_dir() {
    local data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/ps1-tracker"
    mkdir -p "$data_dir"
    ok "Data directory: $data_dir"
}

# ── systemd system service ─────────────────────────────────────────────────────
install_service() {
    local service_file="/etc/systemd/system/$SERVICE_NAME.service"
    info "Installing systemd service (requires sudo)..."

    sudo tee "$service_file" > /dev/null <<EOF
[Unit]
Description=PS1 Game Tracker Daemon + API
After=network.target

[Service]
ExecStart=$VENV_DIR/bin/uvicorn daemon.main:app --host 0.0.0.0 --port 8080
WorkingDirectory=$SCRIPT_DIR
Restart=always
RestartSec=5
User=$CURRENT_USER

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    ok "Service installed: $service_file"
    info "User: $CURRENT_USER"
    info "WorkingDirectory: $SCRIPT_DIR"
}

# ── git init (if needed) ───────────────────────────────────────────────────────
ensure_git() {
    if [[ ! -d "$SCRIPT_DIR/.git" ]]; then
        info "Initializing git repository..."
        git -C "$SCRIPT_DIR" init -q
        ok "Git repository initialized"
    fi
}

# ── main ───────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo "=== PS1 Game Tracker — Installation ==="
    echo ""

    check_python
    setup_venv
    setup_config
    setup_data_dir
    install_service

    echo ""
    echo "=== Installation complete ==="
    echo ""
    echo "Next steps:"
    echo "  1. Edit $SCRIPT_DIR/config.toml"
    echo "     (check process name with: ps aux | grep -i duck)"
    echo "  2. sudo systemctl enable $SERVICE_NAME"
    echo "  3. sudo systemctl start $SERVICE_NAME"
    echo "  4. sudo systemctl status $SERVICE_NAME"
    echo "  5. Open http://localhost:8080"
    echo ""
}

main "$@"
