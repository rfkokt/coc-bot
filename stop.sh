#!/usr/bin/env bash
# Matiin bot worker + backend (:5050) + FE (:5174). BlueStacks dibiarkan (game).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ADB="/Applications/BlueStacks.app/Contents/MacOS/hd-adb"

# 1) Bot worker (via bot.pid, fallback pkill)
if [ -f "$HERE/bot.pid" ]; then
  kill "$(cat "$HERE/bot.pid" 2>/dev/null)" 2>/dev/null && echo "■ bot (bot.pid) dihentikan"
  rm -f "$HERE/bot.pid"
fi
pkill -f "venv/bin/python.*-u bot.py" 2>/dev/null && echo "■ bot (fallback) dihentikan"

# 2) Backend (:5050)
lsof -tiTCP:5050 -sTCP:LISTEN 2>/dev/null | xargs -r kill 2>/dev/null && echo "■ backend (:5050) dihentikan"

# 3) FE vite (:5174)
lsof -tiTCP:5174 -sTCP:LISTEN 2>/dev/null | xargs -r kill 2>/dev/null && echo "■ FE (:5174) dihentikan"

# 4) BlueStacks (opsional — uncomment kalau mau ikut dimatiin)
# osascript -e 'quit app "BlueStacks"' 2>/dev/null && echo "■ BlueStacks dihentikan"

sleep 1
echo "Selesai. Sisa:"
ps -A -o pid,args | grep -E "dashboard\.py|bot\.py|node.*vite" | grep -v grep || echo "  bersih"
