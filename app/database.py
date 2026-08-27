from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False)
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
    if settings.DATABASE_URL.startswith("sqlite"):
        # Ensure subscription columns exist on the existing users table.
        import aiosqlite
        db_path = settings.DATABASE_URL.split("///", 1)[1]
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute("PRAGMA table_info(users)")
            rows = await cur.fetchall()
            existing = {r[1] for r in rows}
            if "plan" not in existing:
                await conn.execute(
                    "ALTER TABLE users ADD COLUMN plan VARCHAR(20) DEFAULT 'free'"
                )
            if "stripe_customer_id" not in existing:
                await conn.execute(
                    "ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255)"
                )
            if "stripe_subscription_id" not in existing:
                await conn.execute(
                    "ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(255)"
                )
            await conn.commit()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
