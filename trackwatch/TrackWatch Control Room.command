#!/bin/bash
# TrackWatch Control Room — one-click launcher for the private review queue.
#
# Double-click this file in Finder (or run it directly) to:
#   1. find the gulfsouthdrags repo reliably (relative to this file, not $PWD)
#   2. check whether the review server is already running on localhost:8765
#   3. start it in the background if it isn't
#   4. wait briefly for it to respond
#   5. open http://localhost:8765/ in your default browser
#
# Does not touch TrackWatch's detection logic or the public website.
# The server only ever binds to 127.0.0.1 — see review_server.py.

set -u

HOST="127.0.0.1"
PORT="8765"
URL="http://${HOST}:${PORT}/"

# Resolve the repo location from this file's own path, not the caller's
# working directory — so double-clicking from Finder always works.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_PY="$REPO_ROOT/trackwatch/review_server.py"
LOG_DIR="$REPO_ROOT/trackwatch/logs"
LOG_FILE="$LOG_DIR/control_room.log"

echo "TrackWatch Control Room"
echo "------------------------"
echo "Repo:   $REPO_ROOT"
echo "Server: $SERVER_PY"
echo

fail() {
  echo "❌ $1"
  echo
  read -n 1 -s -r -p "Press any key to close this window..."
  echo
  exit 1
}

is_up() {
  local code
  code="$(curl -s -o /dev/null -m 2 -w '%{http_code}' "$URL" 2>/dev/null)"
  [[ "$code" == 2* ]]
}

if [ ! -f "$SERVER_PY" ]; then
  fail "Could not find review_server.py at:
  $SERVER_PY

This launcher expects to live inside the trackwatch/ folder of the
gulfsouthdrags repo, right next to review_server.py. If you moved it,
move it back or update the paths in this script."
fi

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 was not found on this Mac. Install Python 3, then try again."
fi

if is_up; then
  echo "✅ TrackWatch review server is already running at $URL"
else
  echo "Starting TrackWatch review server..."
  mkdir -p "$LOG_DIR"
  # Detached background process: closing this window must not kill the
  # server, and this window must not have to stay open to keep it alive.
  ( cd "$REPO_ROOT" && nohup python3 "$SERVER_PY" >>"$LOG_FILE" 2>&1 & disown )

  echo -n "Waiting for it to come up"
  up=0
  for _ in $(seq 1 20); do
    if is_up; then
      up=1
      break
    fi
    echo -n "."
    sleep 0.5
  done
  echo

  if [ "$up" -ne 1 ]; then
    fail "TrackWatch review server did not respond at $URL after 10 seconds.

Check the log for details:
  $LOG_FILE

Common causes: another process is already using port $PORT for something
else, or python3 couldn't start review_server.py (see the log)."
  fi
  echo "✅ Server is up at $URL"
fi

echo "Opening $URL in your default browser..."
open "$URL" || fail "Could not open the browser automatically. Open this URL manually:
  $URL"

echo
echo "This window can be closed — the server keeps running in the background."
echo "To stop it later: pkill -f trackwatch/review_server.py"
sleep 2
