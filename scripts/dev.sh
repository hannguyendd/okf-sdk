#!/usr/bin/env bash
# Launch the OKF dev stack: MCP server, web API (backend), and web frontend.
#
#   scripts/dev.sh [--only mcp,be,web] [--web web2|web] [--read-only]
#
#   mcp  okf-mcp over streamable-http   http://127.0.0.1:$MCP_PORT/mcp  (default 47800)
#   be   okf-web API                    http://127.0.0.1:$BE_PORT       (default 47801)
#   web  frontend dev server            http://localhost:$WEB_PORT      (default 47802)
#        okf-web2 (Vite) by default, or the okf-web frontend with --web web
#
# Ports: defaults sit in an uncommon range; a busy default moves to the next
# free port. A port you set (MCP_PORT, BE_PORT, WEB_PORT) is used as is, and
# the script stops if it is taken. OKF_HOME, OKF_WORKSPACE, OKF_BUNDLE and the
# OKF_EMBEDDING_* variables pass through (or put them in the repo-root .env).
# Ctrl-C stops everything; if one service exits, the rest are stopped too.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ONLY="mcp,be,web"
WEB="web2"
BE_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) ONLY="$2"; shift 2 ;;
    --web) WEB="$2"; shift 2 ;;
    --read-only) BE_ARGS+=(--read-only); shift ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; exit 2 ;;
  esac
done


case "$WEB" in
  web2) WEB_DIR="$ROOT/packages/okf-web2" ;;
  web)  WEB_DIR="$ROOT/packages/okf-web/frontend" ;;
  *) echo "error: --web must be web2 or web" >&2; exit 2 ;;
esac

want() { [[ ",$ONLY," == *",$1,"* ]]; }

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

# The frontend proxies to BE_PORT, so pick it even when only `web` runs.
want mcp && pick_port mcp MCP_PORT 47800
if want be; then pick_port be BE_PORT 47801; else BE_PORT="${BE_PORT:-47801}"; fi
want web && pick_port web WEB_PORT 47802

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

# Job control puts each service in its own process group, so cleanup can stop
# the whole tree (uv → python, bun → vite) without signalling our caller.
set -m
PIDS=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill -TERM -- "-$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM   # exit runs cleanup via the EXIT trap

# Run a command in the background with its output prefixed by a coloured tag.
run() {
  local tag="$1" color="$2"; shift 2
  (
    exec "$@" 2>&1 | while IFS= read -r line; do
      printf '\033[%sm[%s]\033[0m %s\n' "$color" "$tag" "$line"
    done
  ) &
  PIDS+=("$!")
}

if want mcp; then
  run mcp 35 uv run okf-mcp --transport streamable-http --port "$MCP_PORT"
  echo "mcp  → http://127.0.0.1:$MCP_PORT/mcp"
fi
if want be; then
  run be 36 uv run okf-web --port "$BE_PORT" ${BE_ARGS[@]+"${BE_ARGS[@]}"}
  echo "be   → http://127.0.0.1:$BE_PORT"
fi
if want web; then
  if [[ "$WEB" == web2 ]]; then
    WEB_CMD="exec bun run dev --port $WEB_PORT --strictPort"
  else
    WEB_CMD="exec bun run dev"   # dev.ts reads PORT
  fi
  run web 33 env OKF_API="http://127.0.0.1:$BE_PORT" PORT="$WEB_PORT" bash -c "cd '$WEB_DIR' && $WEB_CMD"
  echo "web  → http://localhost:$WEB_PORT  ($WEB)"
fi

[[ ${#PIDS[@]} -gt 0 ]] || { echo "nothing to run (--only $ONLY)" >&2; exit 2; }
set +m   # groups are already assigned; this just silences job notices

# Stop everything as soon as any one service exits (bash 4.3+ has `wait -n`;
# macOS /bin/bash 3.2 polls instead).
if (( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 3) )); then
  wait -n || true
else
  while :; do
    for pid in "${PIDS[@]}"; do kill -0 "$pid" 2>/dev/null || break 2; done
    sleep 1
  done
fi
echo "a service exited; stopping the rest" >&2
