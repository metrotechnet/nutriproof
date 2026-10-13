#!/bin/bash
#
# Build a ZIP package for macOS users to run the web app locally (no signing).
# The package includes a start.command launcher that bootstraps a venv and
# starts the Python server.
#
# Usage:
#   ./build-mac-local-zip.sh
#   ./build-mac-local-zip.sh --output-dir dist
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/dist"
PKG_NAME="NutriProof-mac-local"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./build-mac-local-zip.sh [--output-dir <path>]"
            exit 1
            ;;
    esac
done

STAGE_ROOT="$OUTPUT_DIR/$PKG_NAME"
ZIP_PATH="$OUTPUT_DIR/$PKG_NAME.zip"

echo "=== Building macOS local-run ZIP ==="
echo "Project root: $PROJECT_ROOT"
echo "Output dir:   $OUTPUT_DIR"

rm -rf "$STAGE_ROOT"
mkdir -p "$STAGE_ROOT"
mkdir -p "$OUTPUT_DIR"

copy_required_path() {
    local rel="$1"
    local src="$PROJECT_ROOT/$rel"
    local dst="$STAGE_ROOT/$rel"
    if [ ! -e "$src" ]; then
        echo "Required path not found: $rel"
        exit 1
    fi
    mkdir -p "$(dirname "$dst")"
    cp -R "$src" "$dst"
}

copy_required_path "app.py"
copy_required_path "requirements.txt"
copy_required_path "api"
copy_required_path "dbase"
copy_required_path "static"
copy_required_path "templates"
copy_required_path ".env.example"

cat > "$STAGE_ROOT/start.command" <<'EOF'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it first (python.org or Homebrew)."
  exit 1
fi

if ! command -v tesseract >/dev/null 2>&1; then
  echo "Tesseract is required for OCR."
  echo "Install with: brew install tesseract tesseract-lang"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

export UPLOAD_ROOT="${UPLOAD_ROOT:-$HOME/NutriProof/uploads}"
export PORT="${PORT:-8080}"
mkdir -p "$UPLOAD_ROOT"

echo "Starting NutriProof server..."
echo "URL: http://localhost:$PORT/main"
echo "Data folder: $UPLOAD_ROOT"

python app.py
EOF

cat > "$STAGE_ROOT/README_MAC_LOCAL.txt" <<'EOF'
NutriProof - Local web app package for macOS (unsigned)
========================================================

Requirements:
- macOS
- Python 3
- Tesseract OCR with language data:
  brew install tesseract tesseract-lang

How to run:
1) Double-click "start.command"
2) If macOS blocks it, allow it from:
   System Settings -> Privacy & Security -> Open Anyway
3) Open your browser at:
   http://localhost:8080/main

Optional configuration:
- Copy .env.example to .env and edit values
- Default upload folder: ~/NutriProof/uploads
EOF

chmod +x "$STAGE_ROOT/start.command"

rm -f "$ZIP_PATH"
(
    cd "$OUTPUT_DIR"
    /usr/bin/zip -r "$ZIP_PATH" "$PKG_NAME" >/dev/null
)

echo "Package created:"
echo "  $ZIP_PATH"
echo ""
echo "Contents:"
echo "  $PKG_NAME/start.command"
echo "  $PKG_NAME/README_MAC_LOCAL.txt"
echo "  $PKG_NAME/app.py"
echo "  $PKG_NAME/api/"
echo "  $PKG_NAME/dbase/"
echo "  $PKG_NAME/static/"
echo "  $PKG_NAME/templates/"
echo "  $PKG_NAME/requirements.txt"

