#!/usr/bin/env bash
# Export the Structurizr workspace of a git revision with the Structurizr CLI.
#
# Usage: export-workspace.sh <git-rev | --working-tree> <format> <output-dir>
#
#   <git-rev>       any revision git understands (a SHA, origin/main, ...). The
#                   revision is checked out into a temporary `git worktree`, so
#                   relative paths used by `!adrs`, `!docs` and `!include` resolve
#                   exactly as they did in that revision.
#   --working-tree  export the current checkout as it is on disk.
#   <format>        any Structurizr CLI export format: json, plantuml/c4plantuml, ...
#   <output-dir>    created if missing; the CLI writes its files here.
#
# Environment (both have defaults, override them from the workflow `env`):
#   WORKSPACE              path of the DSL file, relative to the repository root
#   STRUCTURIZR_CLI_IMAGE  Docker image of the Structurizr CLI
#
# Shared by the CI workflows (adr-guard.yml, and the diagram preview workflow).
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <git-rev | --working-tree> <format> <output-dir>" >&2
  exit 2
fi

rev="$1"
format="$2"
output_dir="$3"

WORKSPACE="${WORKSPACE:-docs/architecture/workspace.dsl}"
STRUCTURIZR_CLI_IMAGE="${STRUCTURIZR_CLI_IMAGE:-structurizr/cli:2025.11.09}"

repo_root="$(git rev-parse --show-toplevel)"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"

if [ "$rev" = "--working-tree" ]; then
  rev="the working tree"
  source_root="$repo_root"
else
  tmp="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/export-workspace.XXXXXX")"
  source_root="$tmp/src"
  cleanup() {
    git -C "$repo_root" worktree remove --force "$source_root" >/dev/null 2>&1 || true
    rm -rf "$tmp"
  }
  trap cleanup EXIT
  git -C "$repo_root" worktree add --quiet --detach "$source_root" "$rev"
fi

if [ ! -f "$source_root/$WORKSPACE" ]; then
  echo "error: $WORKSPACE does not exist in $rev" >&2
  exit 1
fi

echo "Exporting $WORKSPACE at $rev as $format into $output_dir" >&2
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$source_root:/usr/local/structurizr:ro" \
  -v "$output_dir:/output" \
  "$STRUCTURIZR_CLI_IMAGE" \
  export -workspace "$WORKSPACE" -format "$format" -output /output >&2
