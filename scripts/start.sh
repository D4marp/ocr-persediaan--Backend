#!/bin/sh
set -e

cd /app/python
uvicorn main:app --host 127.0.0.1 --port 8090 &
WORKER_PID=$!

# Tunggu worker siap
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf http://127.0.0.1:8090/health > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

cd /app
trap "kill $WORKER_PID 2>/dev/null" EXIT INT TERM
exec ./server
