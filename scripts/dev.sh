#!/usr/bin/env bash
# Launch the OKF stack: MCP server, web API (backend), and web frontend.
#
#   scripts/dev.sh [--only mcp,be,web] [--web web2|web] [--prod] [-d] [--read-only]
#   scripts/dev.sh stop | status
#
#   mcp  okf-mcp over streamable-http   http://127.0.0.1:$MCP_PORT/mcp  (default 47800)
#   be   okf-web API                    http://127.0.0.1:$BE_PORT       (default 47801)
#   web  frontend dev server            http://localhost:$WEB_PORT      (default 47802)
#        okf-web2 (Vite) by default, or the okf-web frontend with --web web
#
#   --prod        build the frontend once and let the backend serve it (no
#                 dev server; the UI is at the be URL). `web` implies `be`.
#   -d, --detach  run in the background; logs and pids go to .okf-dev/.
#                 `stop` ends a detached run, `status` shows what is up.
#
# Ports: defaults sit in an uncommon range; a busy default moves to the next
# free port. A port you set (MCP_PORT, BE_PORT, WEB_PORT) is used as is, and
# the script stops if it is taken. OKF_HOME, OKF_WORKSPACE, OKF_BUNDLE and the
# OKF_EMBEDDING_* variables pass through (or put them in the repo-root .env).
# In the foreground, Ctrl-C stops everything; if one service exits, the rest
# are stopped too.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STATE="$ROOT/.okf-dev"
ONLY="mcp,be,web"
WEB="web2"
PROD=0
DETACH=0
CMD=start
BE_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    stop|status) CMD="$1"; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    --web) WEB="$2"; shift 2 ;;
    --prod) PROD=1; shift ;;
    -d|--detach) DETACH=1; shift ;;
    --read-only) BE_ARGS+=(--read-only); shift ;;
    -h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; exit 2 ;;
  esac
done

# --- stop / status of a detached run ----------------------------------------

alive() { kill -0 "$1" 2>/dev/null; }

if [[ "$CMD" != start ]]; then
  shopt -s nullglob
  files=("$STATE"/*.pid)
  if [[ ${#files[@]} -eq 0 ]]; then echo "nothing running (no detached run)"; exit 0; fi
  for f in "${files[@]}"; do
    name="$(basename "$f" .pid)"; read -r pid url < "$f"
    if [[ "$CMD" == stop ]]; then
      if alive "$pid"; then kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true; fi
      rm -f "$f"; echo "stopped $name"
    elif alive "$pid"; then
      echo "$name  up    $url  (pid $pid, log .okf-dev/$name.log)"
    else
      echo "$name  down  (log .okf-dev/$name.log)"
    fi
  done
  exit 0
fi

# --- start ------------------------------------------------------------------

case "$WEB" in
  web2) WEB_DIR="$ROOT/packages/okf-web2"; WEB_DIST="$WEB_DIR/dist" ;;
  web)  WEB_DIR="$ROOT/packages/okf-web/frontend"; WEB_DIST="" ;;  # builds into okf-web's bundled static dir
  *) echo "error: --web must be web2 or web" >&2; exit 2 ;;
esac

want() { [[ ",$ONLY," == *",$1,"* ]]; }

# In prod the backend serves the built UI, so `web` means "build, then be".
if (( PROD )) && want web && ! want be; then ONLY+=",be"; fi

if (( DETACH )); then
  shopt -s nullglob
  for f in "$STATE"/*.pid; do
    read -r pid _ < "$f"
    if alive "$pid"; then echo "error: a detached run is already up (scripts/dev.sh status / stop)" >&2; exit 1; fi
  done
  shopt -u nullglob
fi

# True if something is listening on the port (IPv4 or IPv6 loopback).
port_busy() {
  if command -v lsof >/dev/null; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
  fi
}

TAKEN=" "
# pick_port NAME VAR DEFAULT: an explicit $VAR must be free; otherwise the
# first free port from DEFAULT up, skipping ports already picked here.
pick_port() {
  local name="$1" var="$2" port="${!2:-}"
  if [[ -n "$port" ]]; then
    if port_busy "$port"; then
      echo "error: $var=$port is already in use (needed by $name)" >&2; exit 1
    fi
  else
    port="$3"
    while port_busy "$port" || [[ "$TAKEN" == *" $port "* ]]; do
      port=$((port + 1))
      (( port <= $3 + 100 )) || { echo "error: no free port near $3 for $name" >&2; exit 1; }
    done
    [[ "$port" == "$3" ]] || echo "$name: port $3 is in use, using $port" >&2
  fi
  TAKEN+="$port "
  printf -v "$var" '%s' "$port"
}

# The dev frontend proxies to BE_PORT, so pick it even when only `web` runs.
want mcp && pick_port mcp MCP_PORT 47800
if want be; then pick_port be BE_PORT 47801; else BE_PORT="${BE_PORT:-47801}"; fi
want web && (( ! PROD )) && pick_port web WEB_PORT 47802

command -v uv >/dev/null || { echo "error: uv is required" >&2; exit 1; }
if want web; then
  command -v bun >/dev/null || { echo "error: bun is required for the frontend" >&2; exit 1; }
fi

if want mcp || want be; then
  uv sync --quiet
fi
if want web && [[ ! -d "$WEB_DIR/node_modules" ]]; then
  (cd "$WEB_DIR" && bun install)
fi
if want web && (( PROD )); then
  echo "building $WEB frontend…"
  (cd "$WEB_DIR" && bun run build)
  [[ -n "$WEB_DIST" ]] && BE_ARGS+=(--static "$WEB_DIST")
fi

# Job control puts each service in its own process group, so stopping it
# ends the whole tree (uv → python, bun → vite) without signalling our caller.
set -m
PIDS=()
NAMES=()
URLS=()

if (( DETACH )); then
  mkdir -p "$STATE"
  rm -f "$STATE"/*.pid
else
  cleanup() {
    trap - INT TERM EXIT
    for pid in "${PIDS[@]:-}"; do
      [[ -n "$pid" ]] && kill -TERM -- "-$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
  }
  trap cleanup EXIT
  trap 'exit 130' INT TERM   # exit runs cleanup via the EXIT trap
fi

# run NAME COLOR URL CMD...: start a service in the background. Foreground runs
# prefix each output line with a coloured tag; detached runs log to .okf-dev/.
run() {
  local name="$1" color="$2" url="$3"; shift 3
  if (( DETACH )); then
    nohup "$@" > "$STATE/$name.log" 2>&1 < /dev/null &
    echo "$! $url" > "$STATE/$name.pid"
  else
    (
      exec "$@" 2>&1 | while IFS= read -r line; do
        printf '\033[%sm[%s]\033[0m %s\n' "$color" "$name" "$line"
      done
    ) &
  fi
  PIDS+=("$!"); NAMES+=("$name"); URLS+=("$url")
}

if want mcp; then
  run mcp 35 "http://127.0.0.1:$MCP_PORT/mcp" \
    uv run okf-mcp --transport streamable-http --port "$MCP_PORT"
fi
if want be; then
  BE_URL="http://127.0.0.1:$BE_PORT"
  (( PROD )) && want web && BE_URL+="  (serves the $WEB UI)"
  run be 36 "$BE_URL" uv run okf-web --port "$BE_PORT" ${BE_ARGS[@]+"${BE_ARGS[@]}"}
fi
if want web && (( ! PROD )); then
  if [[ "$WEB" == web2 ]]; then
    WEB_CMD="exec bun run dev --port $WEB_PORT --strictPort"
  else
    WEB_CMD="exec bun run dev"   # dev.ts reads PORT
  fi
  run web 33 "http://localhost:$WEB_PORT  ($WEB)" \
    env OKF_API="http://127.0.0.1:$BE_PORT" PORT="$WEB_PORT" bash -c "cd '$WEB_DIR' && $WEB_CMD"
fi

[[ ${#PIDS[@]} -gt 0 ]] || { echo "nothing to run (--only $ONLY)" >&2; exit 2; }
set +m   # groups are already assigned; this just silences job notices

for i in "${!NAMES[@]}"; do printf '%-4s → %s\n' "${NAMES[$i]}" "${URLS[$i]}"; done

if (( DETACH )); then
  sleep 3
  failed=0
  for i in "${!NAMES[@]}"; do
    if ! alive "${PIDS[$i]}"; then
      echo "error: ${NAMES[$i]} exited; see .okf-dev/${NAMES[$i]}.log" >&2; failed=1
    fi
  done
  if (( failed )); then "$0" stop >/dev/null; exit 1; fi
  echo "running in the background — logs in .okf-dev/, stop with: scripts/dev.sh stop"
  exit 0
fi

# Stop everything as soon as any one service exits (bash 4.3+ has `wait -n`;
# macOS /bin/bash 3.2 polls instead).
if (( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 3) )); then
  wait -n || true
else
  while :; do
    for pid in "${PIDS[@]}"; do alive "$pid" || break 2; done
    sleep 1
  done
fi
echo "a service exited; stopping the rest" >&2
