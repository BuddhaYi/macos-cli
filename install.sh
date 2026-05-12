#!/usr/bin/env bash
# install.sh — install macos-cli and all vendored backends
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$SCRIPT_DIR/vendor"

# Pick a PATH target
candidates=("$HOME/.local/bin" "/usr/local/bin" "$HOME/bin")
target=""
for d in "${candidates[@]}"; do
    [[ -d "$d" && -w "$d" ]] && target="$d" && break
done
[[ -z "$target" ]] && { echo "no writable bin in PATH"; exit 1; }

# --- Prereqs ---
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }
command -v node    >/dev/null || { echo "node required (brew install node)"; exit 1; }
command -v npm     >/dev/null || { echo "npm required"; exit 1; }

# pipx or uv for Python tool installs
if command -v pipx >/dev/null; then PYI="pipx install"; PYE="pipx install -e";
elif command -v uv >/dev/null;   then PYI="uv tool install"; PYE="uv tool install -e";
else echo "need pipx or uv (brew install pipx)"; exit 1; fi

echo "==> 1. bird (npm package — link from vendor)"
cd "$VENDOR/bird"
# bird is a fully built npm package — just link it globally
npm link --silent

echo "==> 2. opencli"
cd "$VENDOR/opencli"
npm install --silent
npm run build 2>/dev/null || true
npm link --silent

echo "==> 3. macos-automator-mcp (knowledge base + dist)"
cd "$VENDOR/macos-automator-mcp"
npm install --silent
npm run build 2>/dev/null || true
# we don't need its CLI binary; macli reads the KB directly

echo "==> 4. twitter-cli (editable install)"
$PYE "$VENDOR/twitter-cli"

echo "==> 5. wechat-mcp (editable install — preserves your local patches)"
$PYE "$VENDOR/wechat-mcp"

echo "==> 6. macos-cli main entry (X subsystem absorbed from magpie)"
chmod +x "$SCRIPT_DIR/macli"
ln -sf "$SCRIPT_DIR/macli" "$target/macli"

echo ""
echo "✓ installed: $target/macli → $SCRIPT_DIR/macli"
echo ""
echo "next:"
echo "  macli doctor          # check all backends"
echo "  macli --help          # see all commands"
echo "  macli x cookies-save  # one-time WeChat-like auth for X"
