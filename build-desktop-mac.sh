#!/bin/bash
#
# Build script for NutriProof Electron desktop app (macOS).
#
# Usage:
#   ./build-desktop-mac.sh [--skip-backend] [--skip-electron] [--arch arm64|x64]
#   
# Prerequisites:
#   - Python 3 venv at .venv/
#   - Tesseract installed via Homebrew: brew install tesseract tesseract-lang
#   - Node.js / npm installed
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKIP_BACKEND=false
SKIP_ELECTRON=false
ARCH="$(uname -m)"

# Normalise arch to electron-packager names
if [ "$ARCH" = "arm64" ]; then
    ELECTRON_ARCH="arm64"
elif [ "$ARCH" = "x86_64" ]; then
    ELECTRON_ARCH="x64"
else
    ELECTRON_ARCH="x64"
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-backend)  SKIP_BACKEND=true; shift ;;
        --skip-electron) SKIP_ELECTRON=true; shift ;;
        --arch)          ELECTRON_ARCH="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "=== NutriProof macOS Build ==="
echo "Project root: $PROJECT_ROOT"
echo "Architecture: $ELECTRON_ARCH"

# -------------------------------------------------------------------
# Step 1: Bundle Python backend with PyInstaller
# -------------------------------------------------------------------
if [ "$SKIP_BACKEND" = false ]; then
    echo ""
    echo "--- Step 1: Building Python backend with PyInstaller ---"

    cd "$PROJECT_ROOT"

    VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
    if [ ! -f "$VENV_PYTHON" ]; then
        echo "Error: Virtual environment not found at .venv/. Create it first: python3 -m venv .venv"
        exit 1
    fi

    # Ensure PyInstaller is installed
    "$VENV_PYTHON" -m pip install pyinstaller --quiet

    # Clean previous build
    rm -rf dist/backend build

    # Run PyInstaller
    "$VENV_PYTHON" -m PyInstaller app.spec --noconfirm
    if [ $? -ne 0 ]; then
        echo "Error: PyInstaller failed"
        exit 1
    fi

    # Create uploads folder in dist
    mkdir -p "$PROJECT_ROOT/dist/backend/uploads/main"

    echo "Backend build complete."
fi

# -------------------------------------------------------------------
# Step 2: Bundle Tesseract OCR
# -------------------------------------------------------------------
echo ""
echo "--- Step 2: Bundling Tesseract OCR ---"

TESSERACT_DEST="$PROJECT_ROOT/tesseract-bundle"
rm -rf "$TESSERACT_DEST"

# Detect Homebrew Tesseract location
if [ -d "/opt/homebrew/opt/tesseract" ]; then
    # Apple Silicon Homebrew
    TESSERACT_PREFIX="/opt/homebrew/opt/tesseract"
    TESSDATA_DIR="/opt/homebrew/share/tessdata"
elif [ -d "/usr/local/opt/tesseract" ]; then
    # Intel Homebrew
    TESSERACT_PREFIX="/usr/local/opt/tesseract"
    TESSDATA_DIR="/usr/local/share/tessdata"
else
    echo "Error: Tesseract not found. Install it: brew install tesseract tesseract-lang"
    exit 1
fi

echo "Copying Tesseract from $TESSERACT_PREFIX ..."
mkdir -p "$TESSERACT_DEST/bin" "$TESSERACT_DEST/lib" "$TESSERACT_DEST/share/tessdata"

# Copy binary
cp "$TESSERACT_PREFIX/bin/tesseract" "$TESSERACT_DEST/bin/"

# Copy libraries (Tesseract + Leptonica + dependencies)
for lib in "$TESSERACT_PREFIX"/lib/libtesseract*.dylib; do
    [ -f "$lib" ] && cp -P "$lib" "$TESSERACT_DEST/lib/"
done

# Copy Leptonica libs
LEPT_PREFIX="$(brew --prefix leptonica 2>/dev/null || true)"
if [ -n "$LEPT_PREFIX" ] && [ -d "$LEPT_PREFIX/lib" ]; then
    for lib in "$LEPT_PREFIX"/lib/liblept*.dylib; do
        [ -f "$lib" ] && cp -P "$lib" "$TESSERACT_DEST/lib/"
    done
fi

# Copy tessdata (language files)
if [ -d "$TESSDATA_DIR" ]; then
    cp "$TESSDATA_DIR"/*.traineddata "$TESSERACT_DEST/share/tessdata/" 2>/dev/null || true
fi

# Fix dylib rpaths so the bundled tesseract finds its libs
install_name_tool -add_rpath "@executable_path/../lib" "$TESSERACT_DEST/bin/tesseract" 2>/dev/null || true

echo "Tesseract bundled."

# -------------------------------------------------------------------
# Step 3: Build Electron package
# -------------------------------------------------------------------
if [ "$SKIP_ELECTRON" = false ]; then
    echo ""
    echo "--- Step 3: Building Electron package ---"

    cd "$PROJECT_ROOT/electron"

    npm install
    if [ $? -ne 0 ]; then
        echo "Error: npm install failed"
        exit 1
    fi

    PACK_SCRIPT="pack-mac"
    if [ "$ELECTRON_ARCH" = "arm64" ]; then
        PACK_SCRIPT="pack-mac-arm64"
    fi

    npm run "$PACK_SCRIPT"
    if [ $? -ne 0 ]; then
        echo "Error: electron-packager failed"
        exit 1
    fi

    cd "$PROJECT_ROOT"
    echo "Electron build complete."
fi

# -------------------------------------------------------------------
# Done
# -------------------------------------------------------------------
OUTPUT_DIR="$PROJECT_ROOT/dist/electron/NutriProof-darwin-$ELECTRON_ARCH"
echo ""
echo "=== Build finished ==="
echo "Package output: $OUTPUT_DIR"
if [ -d "$OUTPUT_DIR" ]; then
    TOTAL_MB=$(du -sm "$OUTPUT_DIR" | cut -f1)
    echo "  Total size: ${TOTAL_MB} MB"
    echo "  App: NutriProof.app"
fi
