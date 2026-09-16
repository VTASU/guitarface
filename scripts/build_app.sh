#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"

uv sync --frozen --group dev
uv run python scripts/fetch_model.py
uv run pyinstaller --noconfirm --clean GuitarFace.spec
codesign --verify --deep --strict "dist/Guitar Face.app"

echo "Built and verified: $project_dir/dist/Guitar Face.app"
