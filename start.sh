#!/usr/bin/env bash
# Start BE (BlueStacks + backend :5050) & FE (web/ :5174) barengan.
# Tunggu adb BE ready dulu biar gak "adb gagal konek".
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ADB="/Applications/BlueStacks.app/Contents/MacOS/hd-adb"
BS_APP="/Applications/BlueStacks.app"
BE_PORT=5050
FE_PORT=5174

# 1) BlueStacks (emulator)
if ! pgrep -f "BlueStacks.app/Contents/MacOS/BlueStacks" >/dev/null; then
  echo "▶ Start BlueStacks (emulator)..."
  open -a BlueStacks || open "$BS_APP"
else
  echo "• BlueStacks sudah jalan"
fi

# 2) Tunggu adb localhost:5555 ready (max ~120s)
echo "⏳ Tunggu BE adb siap..."
st=""
for i in $(seq 1 120); do
  st="$("$ADB" -s localhost:5555 get-state 2>/dev/null | tr -d '\r')"
  [ "$st" = "device" ] && break
  sleep 1
done
if [ "$st" != "device" ]; then
  echo "⛔ BE gagal connect dalam 120s. Cek BlueStacks nyala & COC kebuka?" >&2
  exit 1
fi
echo "✅ BE adb siap (localhost:5555 device)"

# 3) Backend (dashboard.py :5050) — restart pakai venv biar fix adb_controller aktif,
#    walau port udah kepakai sama instance stale (system-python).
if lsof -iTCP:"$BE_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "• Backend ($BE_PORT) kepakai → kill stale, restart venv"
  lsof -tiTCP:"$BE_PORT" -sTCP:LISTEN | xargs -r kill 2>/dev/null
  sleep 1
fi
cd "$HERE"
echo "▶ Start backend (dashboard.py :$BE_PORT)"
nohup "$HERE/venv/bin/python" dashboard.py >>backend.log 2>&1 < /dev/null &

# 4) FE (React/Vite di web/ :5174)
if lsof -iTCP:"$FE_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "• FE ($FE_PORT) sudah jalan (skip)"
else
  cd "$HERE/web"
  echo "▶ Start FE (web/ :$FE_PORT)"
  nohup npm run dev >>../fe.log 2>&1 < /dev/null &
fi

echo "✅ BE + FE nyala."
echo "   Buka http://localhost:$FE_PORT  (API backend :$BE_PORT, adb BE :5555)"
