#!/usr/bin/env bash
set -euo pipefail

ENV="${1:-development}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${ROOT}/.dev"
CLEANED_UP=0
BACKEND_PID=""
FRONTEND_PID=""

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

write_pid_files() {
    mkdir -p "${PID_DIR}"
    echo "${BACKEND_PID}" > "${PID_DIR}/backend.pid"
    echo "${FRONTEND_PID}" > "${PID_DIR}/frontend.pid"
}

remove_pid_files() {
    rm -f "${PID_DIR}/backend.pid" "${PID_DIR}/frontend.pid"
}

cleanup() {
    [[ -n "${BACKEND_PID}" ]] && kill_process_tree "${BACKEND_PID}" TERM
    [[ -n "${FRONTEND_PID}" ]] && kill_process_tree "${FRONTEND_PID}" TERM
    sleep 0.3
    [[ -n "${BACKEND_PID}" ]] && kill_process_tree "${BACKEND_PID}" KILL
    [[ -n "${FRONTEND_PID}" ]] && kill_process_tree "${FRONTEND_PID}" KILL
    remove_pid_files
}

on_signal() {
    if [[ "${CLEANED_UP}" -eq 1 ]]; then
        return 0
    fi
    CLEANED_UP=1
    cleanup
    exit 0
}

trap on_signal EXIT INT TERM HUP

cd "${ROOT}"

if [[ ! -d web/node_modules ]]; then
    echo "Installing frontend dependencies..."
    (cd web && pnpm install)
fi

# shellcheck source=scripts/set_env.sh
source "${ROOT}/scripts/set_env.sh" "${ENV}"

printf '\n  Backend API:  http://localhost:8000\n  Frontend UI:  http://localhost:5173  (open this)\n\n'

uv run uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

(cd web && pnpm exec rsbuild dev) &
FRONTEND_PID=$!

write_pid_files

wait "${BACKEND_PID}" "${FRONTEND_PID}" || true
