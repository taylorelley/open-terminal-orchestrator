#!/usr/bin/env bash
# Build and register an OTO sandbox image with OpenShell.
#
# Usage:
#   ./register.sh [slim|full]
#
# Examples:
#   ./register.sh          # Build slim variant (default)
#   ./register.sh full     # Build full variant

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VARIANT="${1:-slim}"

case "$VARIANT" in
  slim)
    DOCKERFILE="Dockerfile"
    TAG="oto-sandbox:slim"
    ;;
  full)
    DOCKERFILE="Dockerfile.full"
    TAG="oto-sandbox:full"
    ;;
  *)
    echo "Unknown variant: $VARIANT (expected 'slim' or 'full')" >&2
    exit 1
    ;;
esac

echo "Building $TAG from $DOCKERFILE..."
docker build -t "$TAG" -f "$SCRIPT_DIR/$DOCKERFILE" "$SCRIPT_DIR"

echo ""
echo "Image built successfully: $TAG"
echo ""
echo "To create a sandbox with this image:"
echo "  openshell sandbox create --from $TAG --name my-sandbox --policy policy.yaml"
echo ""
echo "To register the build context directly with OpenShell:"
echo "  openshell sandbox create --from $SCRIPT_DIR/ --name my-sandbox --policy policy.yaml"
