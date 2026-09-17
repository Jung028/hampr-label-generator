#!/bin/bash
# Double-click in Finder to start the Hampr Label Generator and open it.
# Leave the Terminal window open while you work; closing it stops the server.

cd "$(dirname "$0")/.." || exit 1

URL="http://127.0.0.1:5000/"

if curl -s -o /dev/null "$URL"; then
  echo "Label generator is already running."
else
  echo "Starting label generator..."
  nohup .venv-1/bin/python web/app.py > /tmp/hampr-label-generator.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "$URL" && break
    sleep 0.5
  done
fi

if curl -s -o /dev/null "$URL"; then
  echo "Ready. Opening $URL"
  open "$URL"
else
  echo "Could not start. Check /tmp/hampr-label-generator.log"
  exit 1
fi
