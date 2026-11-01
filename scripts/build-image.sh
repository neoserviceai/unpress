#!/bin/bash
# Build (and optionally push) the Unpress engine image.
# Stages a clean build context: unpress apps + the builder fork.
#
#   BUILDER_SRC=~/GitHub/builder bash scripts/build-image.sh [--push]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# builder-unpress = the `unpress` branch worktree (upstream develop + thin
# Unpress layer). NEVER default to ../builder: that checkout is the v15
# version-15 production branch.
BUILDER_SRC="${BUILDER_SRC:-$REPO_DIR/../builder-unpress}"
IMAGE="${UNPRESS_IMAGE:-ghcr.io/neoserviceai/unpress:latest}"

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

echo "[build] staging context in $STAGE"
mkdir -p "$STAGE/ctx" "$STAGE/docker/single"
rsync -a --exclude node_modules --exclude .git --exclude __pycache__ "$BUILDER_SRC/" "$STAGE/ctx/builder/"
rsync -a --exclude __pycache__ "$REPO_DIR/apps/wp_migrator/" "$STAGE/ctx/wp_migrator/"
rsync -a --exclude __pycache__ "$REPO_DIR/apps/unpress_core/" "$STAGE/ctx/unpress_core/"
cp "$REPO_DIR/docker/single/Dockerfile" "$STAGE/Dockerfile"
cp "$REPO_DIR/docker/single/Procfile.prod" "$STAGE/docker/single/Procfile.prod"
cp "$REPO_DIR/docker/single/entrypoint.sh" "$STAGE/docker/single/entrypoint.sh"

echo "[build] docker build $IMAGE (bench init inside — 15-25 min on first build)"
docker build -t "$IMAGE" "$STAGE"

if [ "${1:-}" = "--push" ]; then
	echo "[build] pushing $IMAGE"
	docker push "$IMAGE"
fi
echo "[build] done: $IMAGE"
