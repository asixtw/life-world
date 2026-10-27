"""Create the project-local environment. Run: python3 scripts/setup.py"""
from pathlib import Path
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / '.venv'
PYTHON = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

if __name__ == '__main__':
    if sys.version_info < (3, 9):
        raise SystemExit('Life World requires Python 3.9 or later')
    if not PYTHON.exists():
        venv.EnvBuilder(with_pip=True).create(ENV)
    subprocess.run([str(PYTHON), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.lock')], check=True)
    print('Ready. Run:', PYTHON, '-m app (from', ROOT, ')')
