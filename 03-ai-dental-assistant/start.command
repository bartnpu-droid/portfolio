#!/bin/bash
# One-click start: installs everything, opens a public HTTPS link for the website chat and runs the assistant.
set -e
cd "$(dirname "$0")"
mkdir -p data bin
echo "== AI receptionist =="

PY=$(command -v python3 || true)
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Python 3.9+ is required: https://www.python.org/downloads/"; exit 1
fi
# Recreate the virtual environment if the folder was moved (its paths are absolute)
if [ -d .venv ] && ! grep -q "$(pwd)/.venv" .venv/bin/activate 2>/dev/null; then rm -rf .venv; fi
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
echo "Installing dependencies..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

PORT=$(python - <<'PYEOF'
import pathlib, re, socket
env = pathlib.Path(".env"); text = env.read_text()
m = re.search(r"^WEB_PORT=(\d+)", text, re.M); port = int(m.group(1)) if m else 8090
def free(p):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # a just-stopped server doesn't count as busy
        try: s.bind(("0.0.0.0", p)); return True
        except OSError: return False
if not free(port):
    port = next(p for p in range(8090, 8200) if free(p))
    text = re.sub(r"^WEB_PORT=.*$", f"WEB_PORT={port}", text, flags=re.M); env.write_text(text)
print(port)
PYEOF
)

# Public HTTPS link for the website demo (optional, uses cloudflared)
CF=$(command -v cloudflared || true)
[ -z "$CF" ] && [ -x ../01-telegram-booking-bot/bin/cloudflared ] && CF=../01-telegram-booking-bot/bin/cloudflared
if [ -z "$CF" ]; then
  CF=./bin/cloudflared
  if [ ! -x "$CF" ]; then
    [ "$(uname -m)" = "arm64" ] && F=cloudflared-darwin-arm64.tgz || F=cloudflared-darwin-amd64.tgz
    curl -fsSL -o bin/cf.tgz "https://github.com/cloudflare/cloudflared/releases/latest/download/$F" \
      && tar -xzf bin/cf.tgz -C bin && rm -f bin/cf.tgz && chmod +x "$CF" || CF=""
  fi
fi
if [ -n "$CF" ]; then
  : > data/tunnel.log
  "$CF" tunnel --no-autoupdate --url "http://localhost:$PORT" > data/tunnel.log 2>&1 &
  TUNNEL_PID=$!
  trap 'kill $TUNNEL_PID 2>/dev/null; wait $TUNNEL_PID 2>/dev/null' EXIT INT TERM
  for i in $(seq 1 40); do
    URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' data/tunnel.log | head -1 || true); [ -n "$URL" ] && break; sleep 1
  done
  [ -n "$URL" ] && export PUBLIC_URL="$URL"
fi

# Open the website in the browser as soon as the server answers
if command -v open >/dev/null; then
  (for i in $(seq 1 40); do
    if curl -s -o /dev/null "http://localhost:$PORT/health"; then open "http://localhost:$PORT"; break; fi; sleep 1
  done) &
fi

python -m app.main
