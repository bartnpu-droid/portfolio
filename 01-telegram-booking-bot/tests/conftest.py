import os
import sys
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("ADMIN_IDS", "5")
os.environ.setdefault("LANGUAGES", "en")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
