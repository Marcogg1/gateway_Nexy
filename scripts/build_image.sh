#!/usr/bin/env bash
# Build dev Docker image and write a tar for LuCI upload.
#
# Output is a classic single-manifest Docker tar (no attestations, no manifest
# list) so the legacy dockerd on the gateway / LuCI dockerman can parse it.
#
# Each build gets a short timestamp tag (e.g. gateway:dev05121525, encoding
# month/day/hour/minute) so re-uploading does not strip the tag from a
# previous image and break the container's image reference. Override with
# IMAGE_TAG=... .
#
# The .tar is written to build/gateway-dev.tar (fixed filename, overwritten
# each run) so only the latest build is kept locally. The build/ directory
# is gitignored and dockerignored so old tars do not bloat the next image.
# Override with OUTPUT=... .
#
# Deploy:
#   1. LuCI > Docker > Images > Load             -> upload the .tar
#   2. LuCI > Docker > Containers > <slot>       -> edit Image field to the
#                                                   new tag, Save -> recreate
#   3. Run Application = ON so ENTRYPOINT fires (starts sshd).
set -euo pipefail

STAMP="$(date +%m%d%H%M)"
IMAGE_TAG="${IMAGE_TAG:-gateway:dev${STAMP}}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.dev}"
PLATFORM="${PLATFORM:-linux/arm64}"
OUTPUT="${OUTPUT:-build/gateway-dev.tar}"
mkdir -p "$(dirname "$OUTPUT")"

export DOCKER_BUILDKIT=1

echo "==> Building $IMAGE_TAG ($PLATFORM) from $DOCKERFILE -> $OUTPUT"
docker buildx build \
    --platform "$PLATFORM" \
    -f "$DOCKERFILE" \
    -t "$IMAGE_TAG" \
    --provenance=false \
    --sbom=false \
    --output "type=docker,dest=$OUTPUT" \
    .

SIZE="$(du -h "$OUTPUT" | cut -f1)"
echo
echo "Built: $OUTPUT ($SIZE)"
echo "Tag:   $IMAGE_TAG"
echo
echo "Next:"
echo "  1. LuCI > Docker > Images > Load -> upload $OUTPUT"
echo "  2. LuCI > Docker > Containers > <slot> -> edit Image to '$IMAGE_TAG' -> Save"
