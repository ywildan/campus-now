#!/usr/bin/env bash
#
# install-desktop-integration.sh
#
# Installs Campus Now's desktop integration:
#   1. Noctalia v5 bar widget plugin
#   2. Systemd user service (web dashboard on :8888)
#
# Portability: paths in the copied files use %h / ~ (HOME-relative), so this
# works regardless of where your home directory lives, as long as the project
# is at $HOME/Projects/campus-now.
#
# This script does NOT touch Noctalia's settings.toml. Enabling the plugin
# and adding the widget to the bar are left manual (see README) because they
# depend on your bar layout.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NOCTALIA_PLUGIN_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/noctalia/plugins/campus-now"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "Campus Now desktop integration installer"
echo "----------------------------------------"
echo "Project dir : $PROJECT_DIR"
echo "Noctalia    : $NOCTALIA_PLUGIN_DIR"
echo "Systemd     : $SYSTEMD_USER_DIR"
echo

# --- 1. Noctalia plugin -----------------------------------------------
echo "[1/3] Installing Noctalia v5 widget plugin..."
mkdir -p "$NOCTALIA_PLUGIN_DIR"
cp "$PROJECT_DIR/integrations/noctalia/plugin.toml" "$NOCTALIA_PLUGIN_DIR/"
cp "$PROJECT_DIR/integrations/noctalia/widget.luau" "$NOCTALIA_PLUGIN_DIR/"
echo "      Copied plugin.toml + widget.luau -> $NOCTALIA_PLUGIN_DIR"

# --- 2. Systemd user service ------------------------------------------
echo "[2/3] Installing systemd user service..."
mkdir -p "$SYSTEMD_USER_DIR"
cp "$PROJECT_DIR/integrations/systemd/campus-now.service" "$SYSTEMD_USER_DIR/"
systemctl --user daemon-reload
systemctl --user enable --now campus-now.service
echo "      Enabled + started campus-now.service"

# --- 3. Noctalia plugin enable (manual step hint) ----------------------
echo "[3/3] Done installing files."
echo
echo "Next, enable the Noctalia plugin and add the widget to your bar:"
echo
echo "  noctalia msg plugins enable noctalia/campus-now"
echo "  noctalia config validate"
echo
echo "Then, in Noctalia Settings -> Bar, add the 'Campus Now' widget to"
echo "your bar (type: noctalia/campus-now:next-class), or add to the bar"
echo "center list in your Noctalia config."
echo
echo "If the service was already running, check it:"
echo "  systemctl --user status campus-now.service"
echo "  curl -s http://localhost:8888/api/status"