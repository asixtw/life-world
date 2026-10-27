#!/bin/zsh
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  print "請先執行：python3 scripts/setup.py"
  exit 1
fi
exec .venv/bin/python -m app
