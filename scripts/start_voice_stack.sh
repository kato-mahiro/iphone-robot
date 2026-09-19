#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
hayamimi_python="$project_dir/hayamimi/.venv/bin/python"
robot_host=${ROBOT_HOST:-"$(scutil --get LocalHostName).local"}

command -v caddy >/dev/null || { echo "error: caddy is not installed" >&2; exit 1; }
command -v nc >/dev/null || { echo "error: nc is not installed" >&2; exit 1; }
test -x "$hayamimi_python" || { echo "error: Hayamimi venv is missing" >&2; exit 1; }

for port in 8443 8766 8833; do
	if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
		echo "error: port $port is already in use; stop the existing voice stack first" >&2
		exit 1
	fi
done

mkdir -p "$project_dir/logs"
export ROBOT_HOST="$robot_host"

"$hayamimi_python" -u "$project_dir/hayamimi/scripts/realtime_transcribe.py" \
	--input ws --ws-host 127.0.0.1 --ws-port 8766 --serve 8833 \
	--mode single --lang ja --no-refine \
	>>"$project_dir/logs/hayamimi.log" 2>&1 &
hayamimi_pid=$!

cd "$project_dir"
caddy run --config Caddyfile >>"$project_dir/logs/caddy.log" 2>&1 &
caddy_pid=$!

cleanup() {
	trap - EXIT INT TERM
	kill "$caddy_pid" "$hayamimi_pid" 2>/dev/null || true
	wait "$caddy_pid" "$hayamimi_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=false
i=0
while [ "$i" -lt 90 ]; do
	if ! kill -0 "$hayamimi_pid" 2>/dev/null || ! kill -0 "$caddy_pid" 2>/dev/null; then
		echo "error: startup failed; check logs/hayamimi.log and logs/caddy.log" >&2
		exit 1
	fi
	if nc -z 127.0.0.1 8766 2>/dev/null && nc -z 127.0.0.1 8833 2>/dev/null && \
		curl -ksS --resolve "$robot_host:8443:127.0.0.1" "https://$robot_host:8443/" >/dev/null 2>&1; then
		ready=true
		break
	fi
	i=$((i + 1))
	sleep 1
done

if [ "$ready" != true ]; then
	echo "error: server did not become ready; check logs/hayamimi.log and logs/caddy.log" >&2
	exit 1
fi

echo "voice stack ready"
echo "iPhone URL: https://$robot_host:8443/"
echo "Hayamimi log: $project_dir/logs/hayamimi.log"
echo "Client log:    $project_dir/logs/caddy-access.log"
echo "stop: Ctrl-C"

while kill -0 "$hayamimi_pid" 2>/dev/null && kill -0 "$caddy_pid" 2>/dev/null; do
	sleep 1
done

echo "error: a voice-stack process stopped; check logs" >&2
exit 1
