#!/usr/bin/env bash
# Installs Desktop Hamster for the current user on Ubuntu.
set -e

DEST="$HOME/.local/share/desktop-hamster"
APPS="$HOME/.local/share/applications"

echo "Installing PyQt5 (needs your password)..."
sudo apt-get update -qq
sudo apt-get install -y python3-pyqt5 x11-utils

mkdir -p "$DEST" "$APPS"
SRC="$(cd "$(dirname "$0")" && pwd)"
cp "$SRC/hamster.py" "$DEST/hamster.py"
cp "$SRC/version.json" "$DEST/version.json"
rm -rf "$DEST/sprites" && cp -r "$SRC/sprites" "$DEST/sprites"
cp "$SRC/message.txt" "$DEST/message.txt" 2>/dev/null || true
chmod +x "$DEST/hamster.py"

cat > "$APPS/desktop-hamster.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desktop Hamster
Comment=A little hamster that lives on your desktop
Exec=python3 $DEST/hamster.py
Icon=face-smile
Terminal=false
Categories=Game;
EOF

echo
echo "Done. Open the app grid and search 'Desktop Hamster', or run:"
echo "  python3 $DEST/hamster.py"
echo "Right-click the hamster -> 'Start on login' to have it show up every time."
