#!/bin/sh
cd "$(dirname "$0")"
python3 -m pip install --quiet pypdf 2>/dev/null
python3 main.py
