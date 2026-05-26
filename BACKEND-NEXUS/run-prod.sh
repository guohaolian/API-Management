#!/usr/bin/env bash
set -euo pipefail

uv run robyn -m app --process=4 --workers=3