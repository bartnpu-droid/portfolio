#!/bin/bash
# One-click start: installs everything, opens an HTTPS tunnel for the Mini App and runs the bot.
set -e
cd "$(dirname "$0")"
mkdir -p data bin
echo "== Barbershop bot =="

PY=$(command -v python3 || true)
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Python 3.9+ is required. Download it from https://www.python.org/downloads/ and run this again."
  exit 1
fi

# Recreate the virtual environment if the folder was moved (its paths are absolute)
if [ -d .venv ] && ! .venv/bin/python -c "import sys" >/dev/null 2>&1; then rm -rf .venv; fi
if [ -d .venv ] && ! grep -q "$(pwd)/.venv" .venv/bin/activate 2>/dev/null; then rm -rf .venv; fi
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
echo "Installing dependencies (first run takes a minute)..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

CF=$(command -v cloudflared || true)
if [ -z "$CF" ]; then
  CF=./bin/cloudflared
  if [ ! -x "$CF" ]; then
    echo "Downloading cloudflared (HTTPS tunnel for the Mini App)..."
    [ "$(uname -m)" = "arm64" ] && F=cloudflared-darwin-arm64.tgz || F=cloudflared-darwin-amd64.tgz
    curl -fsSL -o bin/cf.tgz "https://github.com/cloudflare/cloudflared/releases/latest/download/$F"
    tar -xzf bin/cf.tgz -C bin && rm -f bin/cf.tgz
    chmod +x "$CF"
  fi
fi

# Use WEB_PORT from .env; if that port is busy, pick a free one and save it.
PORT=$(python - <<'PYEOF'
import pathlib, re, socket
env = pathlib.Path(".env")
text = env.read_text()
m = re.search(r"^WEB_PORT=(\d+)", text, re.M)
port = int(m.group(1)) if m else 8080

def free(p):
    with socket.socket() as s:
        try:
            s.bind(("0.0.0.0", p)); return True
        except OSError:
            return False

if not free(port):
    port = next(p for p in range(8765, 8900) if free(p))
    text = re.sub(r"^WEB_PORT=.*$", f"WEB_PORT={port}", text, flags=re.M) if m else text + f"\nWEB_PORT={port}\n"
    env.write_text(text)
print(port)
PYEOF
)
echo "Web server port: $PORT"
echo "Starting the tunnel..."
: > data/tunnel.log
"$CF" tunnel --no-autoupdate --url "http://localhost:$PORT" > data/tunnel.log 2>&1 &
TUNNEL_PID=$!
trap 'kill $TUNNEL_PID 2>/dev/null; wait $TUNNEL_PID 2>/dev/null' EXIT INT TERM

URL=""
for i in $(seq 1 40); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' data/tunnel.log | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "Could not start the tunnel. Details: data/tunnel.log"
  exit 1
fi

python - "$URL" <<'PYEOF'
import pathlib, re, sys
p = pathlib.Path(".env")
text = p.read_text()
text = re.sub(r"^WEBAPP_URL=.*$", "WEBAPP_URL=" + sys.argv[1], text, flags=re.M)
p.write_text(text)
PYEOF

echo ""
echo "Mini App: $URL"
echo "Starting the bot... Keep this window open. Press Ctrl+C to stop."
python -m app.main
