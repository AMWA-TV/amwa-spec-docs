#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset

shopt -s nullglob

REMARKRC="${REMARKRC:?REMARKRC must be set}"

failed=n

# The shared toolkit is checked out into the repository during CI. It is not
# part of the repository being linted.
find_args=(
    .
    -path './.git' -prune -o
    -path './.amwa-spec-docs' -prune -o
    -path './.lint' -prune -o
    -path './node_modules' -prune -o
    -path './.render' -prune -o
    -name '*.md' -print0
)

echo Linting Markdown...
if ! find "${find_args[@]}" | xargs -0 remark --rc-path "${REMARKRC}" --frail; then
    failed=y
fi

if [[ -d APIs ]]; then
    echo Linting APIs...
    for file in APIs/*.raml; do
        perl -pi.bak -e 's/!include//' "${file}"
        if yamllint "${file}" > output; then
            echo "${file}" ok
        else
            cat output
            echo -e "\033[31m${file} failed\033[0m"
            failed=y
        fi
        rm -f output
        mv "${file}.bak" "${file}"
    done
fi

if [[ -d APIs/schemas ]]; then
    echo Linting schemas...
    for file in APIs/schemas/*.json; do
        if jsonlint "${file}" > /dev/null; then
            echo "${file}" ok
        else
            echo -e "\033[31m${file} failed\033[0m"
            failed=y
        fi
    done
fi

if [[ -d examples ]]; then
    echo Linting examples...
    while IFS= read -r -d '' file; do
        if jsonlint "${file}" > /dev/null; then
            echo "${file}" ok
        else
            echo -e "\033[31m${file} failed\033[0m"
            failed=y
        fi
    done < <(find examples -type d -name '.*' -prune -o -type f -name '*.json' -print0)
    while IFS= read -r -d '' file; do
        # shellcheck disable=SC2086
        if sdpoker "${file}" ${SDPOKER_OPTIONS:-}; then
            echo "${file}" ok
        else
            echo -e "\033[31m${file} failed\033[0m"
            failed=y
        fi
    done < <(find examples -type d -name '.*' -prune -o -type f -name '*.sdp' -print0)
fi

if [[ "${failed}" == "y" ]]; then
    exit 1
fi
