#!/bin/bash
# Package Lambda functions with dependencies
# Creates zip files for deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SWOT_ROOT="$(dirname "$PROJECT_ROOT")"
BUILD_DIR="$PROJECT_ROOT/build"

echo "=== Packaging Lambda Functions ==="

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/package"

# Install dependencies
echo "Installing dependencies..."
pip install -r "$SWOT_ROOT/requirements.txt" -t "$BUILD_DIR/package" --quiet

# Copy source code
echo "Copying source code..."
cp -r "$SWOT_ROOT/src" "$BUILD_DIR/package/"
cp -r "$PROJECT_ROOT/lambda" "$BUILD_DIR/package/"
cp -r "$PROJECT_ROOT/dynamodb" "$BUILD_DIR/package/"

# Create zip
echo "Creating deployment package..."
cd "$BUILD_DIR/package"
zip -r "$BUILD_DIR/lambda-package.zip" . -q

echo "Package created: $BUILD_DIR/lambda-package.zip"
echo "Size: $(du -h "$BUILD_DIR/lambda-package.zip" | cut -f1)"

# Upload to S3 (optional)
# aws s3 cp "$BUILD_DIR/lambda-package.zip" s3://swot-agent-deployments/lambda-package.zip

echo "=== Packaging Complete ==="
