#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${ROOT}/.dev"

kill_process_tree() {
    local pid="${1:?}"
    local signal="${2:-TERM}"
    local child

    if ! kill -0 "${pid}" 2>/dev/null; then
        return 0
    fi

    while IFS= read -r child; do
        [[ -z "${child}" ]] && continue
        kill_process_tree "${child}" "${signal}"
    done < <(pgrep -P "${pid}" 2>/dev/null || true)

    kill "-${signal}" "${pid}" 2>/dev/null || true
}

stop_pid_file() {
    local name="${1:?}"
    local pid_file="${PID_DIR}/${name}.pid"

    if [[ ! -f "${pid_file}" ]]; then
        return 1
    fi

    local pid
    pid=$(tr -d '[:space:]' < "${pid_file}")
    if [[ -z "${pid}" ]]; then
        rm -f "${pid_file}"
        return 1
    fi

    echo "Stopping ${name} (pid ${pid})"
    kill_process_tree "${pid}" TERM
    sleep 0.3
    kill_process_tree "${pid}" KILL
    rm -f "${pid_file}"
    return 0
}

kill_port() {
    local port="${1:?}"
    local pids

    pids=$(lsof -ti ":${port}" 2>/dev/null || true)
    if [[ -z "${pids}" ]]; then
        return 0
    fi

    echo "Stopping processes on port ${port}: ${pids//$'\n'/ }"
    # shellcheck disable=SC2086
    kill -TERM ${pids} 2>/dev/null || true
    sleep 0.5

    pids=$(lsof -ti ":${port}" 2>/dev/null || true)
    if [[ -n "${pids}" ]]; then
        # shellcheck disable=SC2086
        kill -KILL ${pids} 2>/dev/null || true
    fi
}

stopped_backend=0
stopped_frontend=0
stop_pid_file backend && stopped_backend=1 || true
stop_pid_file frontend && stopped_frontend=1 || true

if [[ "${stopped_backend}" -eq 0 ]]; then
    kill_port 8000
fi

if [[ "${stopped_frontend}" -eq 0 ]]; then
    kill_port 5173
fi
