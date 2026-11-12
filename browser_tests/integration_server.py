"""獨立合成SQLite瀏覽器伺服器，不連GCP或真AI。"""
from datetime import datetime,timezone
import os
from app.main import create_app
app=create_app(data_dir=os.environ['LIFEWORLD_DATA_DIR'],clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
