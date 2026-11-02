#!/usr/bin/env bash

set -euo pipefail

workflow="${1:-docs.yml}"
ref="${2:-main}"
repo="${3:-}"
gh_args=()

if [[ -n "${repo}" ]]; then
    gh_args+=(--repo "${repo}")
fi

run_url="$(gh workflow run "${workflow}" "${gh_args[@]}" --ref "${ref}")"
run_url="${run_url%/}"
run_id="${run_url##*/}"

if [[ ! "${run_id}" =~ ^[0-9]+$ ]]; then
    echo "gh did not return a workflow run URL: ${run_url}" >&2
    exit 1
fi

echo "Watching workflow run ${run_id}"
exec gh run watch "${run_id}" "${gh_args[@]}" --exit-status
