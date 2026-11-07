#!/bin/bash
# Opens the TACET One landing page in your browser (double-click this file on a Mac).
# The little server tells the browser not to reuse old copies, so you always see the latest version.
cd "$(dirname "$0")/site" || exit 1
PORT=8093
while lsof -i :$PORT >/dev/null 2>&1; do PORT=$((PORT + 1)); done
echo "TACET One: http://localhost:$PORT   (close this window to stop)"
( sleep 1; open "http://localhost:$PORT" ) &
exec python3 - "$PORT" <<'PY'
import http.server, sys
class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()
    def log_message(self, *args):
        pass
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
PY
