#!/bin/bash
set -euo pipefail

function debug() {
    echo "::debug file=${BASH_SOURCE[0]},line=${BASH_LINENO[0]}::$1"
}

function error() {
    echo "::error file=${BASH_SOURCE[0]},line=${BASH_LINENO[0]}::$1"
}

function add_mask() {
    echo "::add-mask::$1"
}

if [ -z "${GITHUB_ACTOR:-}" ]; then
    error "GITHUB_ACTOR environment variable is not set"
    exit 1
fi

if [ -z "${GITHUB_REPOSITORY:-}" ]; then
    error "GITHUB_REPOSITORY environment variable is not set"
    exit 1
fi

if [ -z "${GH_PERSONAL_ACCESS_TOKEN:-}" ]; then
    error "GH_PERSONAL_ACCESS_TOKEN environment variable is not set"
    exit 1
fi

add_mask "${GH_PERSONAL_ACCESS_TOKEN}"

if [ -z "${WIKI_COMMIT_MESSAGE:-}" ]; then
    debug "WIKI_COMMIT_MESSAGE not set, using default"
    WIKI_COMMIT_MESSAGE='Automatically publish wiki'
fi

if [ -z "${INPUT_PATH:-}" ] && [ "${#}" -gt 0 ]; then
    export INPUT_PATH="${1}"
fi

GIT_REPOSITORY_URL="https://${GH_PERSONAL_ACCESS_TOKEN}@github.com/${GITHUB_REPOSITORY}.wiki.git"

debug "Checking out wiki repository"
tmp_dir="$(mktemp -d -t ci-XXXXXXXXXX)"
cleanup() {
    rm -rf "${tmp_dir}"
}
trap cleanup EXIT

(
    cd "${tmp_dir}"
    git init
    git config user.name "${GITHUB_ACTOR}"
    git config user.email "${GITHUB_ACTOR}@users.noreply.github.com"
    git pull "${GIT_REPOSITORY_URL}"
)

debug "Preparing wiki pages from ${INPUT_PATH}"
python3 /publish_wiki.py --dest "${tmp_dir}" --workspace "${GITHUB_WORKSPACE:-$(pwd)}"

debug "Committing and pushing changes"
(
    cd "${tmp_dir}"
    git add -A
    if git diff --cached --quiet; then
        echo "No wiki changes to publish"
        exit 0
    fi
    git commit -m "${WIKI_COMMIT_MESSAGE}"
    git push --set-upstream "${GIT_REPOSITORY_URL}" master
)
