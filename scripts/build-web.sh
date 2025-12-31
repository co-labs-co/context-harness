#!/usr/bin/env bash
# Build script for context-harness with web UI
# This script builds the Next.js frontend and copies it to the package directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔨 Building ContextHarness Web UI..."

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "❌ npm is required to build the web UI"
    echo "   Install Node.js from https://nodejs.org/"
    exit 1
fi

# Build the frontend
echo "📦 Installing frontend dependencies..."
cd web
npm install

echo "🏗️  Building Next.js static export..."
npm run build

# Copy to package directory
echo "📋 Copying static files to package..."
cd "$SCRIPT_DIR"
rm -rf src/context_harness/interfaces/web/static
mkdir -p src/context_harness/interfaces/web/static
cp -r web/out/* src/context_harness/interfaces/web/static/

echo "✅ Web UI built successfully!"
echo ""
echo "Static files location: src/context_harness/interfaces/web/static/"
echo ""
echo "To install and test:"
echo "  uv pip install -e '.[web]'"
echo "  context-harness serve"
