#!/usr/bin/env bash
# Arranque en Arch Linux. Ejecutar desde la raiz del repo.
set -euo pipefail

command -v uv >/dev/null || { echo "Instala uv:  sudo pacman -S uv"; exit 1; }

uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"

echo "== tests =="
pytest -q

echo "== demo end-to-end (datos sinteticos) =="
dtdecoder demo --outdir reports/demo

echo
echo "Listo. Revisa reports/demo/figures/"
echo "Con datos reales:"
echo "  dtdecoder convert --src data/raw --dst data/interim/events.parquet --partition-by match_id"
echo "  dtdecoder phase0 --src data/interim/events.parquet --outdir data/processed"
