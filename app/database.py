from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
engine = create_async_engine(db_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    if db_url.startswith("sqlite"):
        import aiosqlite
        db_path = db_url.split("///", 1)[1]
        if db_path != ":memory:":
            try:
                async with aiosqlite.connect(db_path) as conn:
                    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                    if await cur.fetchone():
                        cur = await conn.execute("PRAGMA table_info(users)")
                        rows = await cur.fetchall()
                        existing = {r[1] for r in rows}
                        if "plan" not in existing:
                            await conn.execute("ALTER TABLE users ADD COLUMN plan VARCHAR(20) DEFAULT 'free'")
                        if "stripe_customer_id" not in existing:
                            await conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255)")
                        if "stripe_subscription_id" not in existing:
                            await conn.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(255)")
                        await conn.commit()
            except Exception:
                pass
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
