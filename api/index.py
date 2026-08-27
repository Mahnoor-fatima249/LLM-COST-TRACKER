import os
import sys
import secrets
from pathlib import Path

VERCEL = os.environ.get("VERCEL", "") == "1"

if VERCEL:
    orig_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(orig_dir))
    os.chdir(str(orig_dir))

    if not os.environ.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
    os.environ["DISABLE_BILLING"] = "true"

    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and db_url.startswith("postgresql://"):
        os.environ["DATABASE_URL"] = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from mangum import Mangum
from app.main import app

handler = Mangum(app)
