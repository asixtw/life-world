from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.main import create_app

if __name__ == '__main__':
    with TemporaryDirectory() as directory:
        schema = create_app(data_dir=directory).openapi()
    (ROOT / 'docs' / 'openapi.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
    print('Exported docs/openapi.json')
