import os
import sys
import secrets
from pathlib import Path

VERCEL = os.environ.get("VERCEL", "") == "1"

if VERCEL:
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_urlsafe(32))
    os.environ["DISABLE_BILLING"] = "true"
    orig_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(orig_dir))
    os.chdir(str(orig_dir))

from mangum import Mangum
from app.main import app

handler = Mangum(app)
