from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings
from core.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Ensure new columns exist for existing databases (SQLite schema evolution)
        try:
            from sqlalchemy import text
            existing_cols_res = await conn.execute(text("PRAGMA table_info(lines)"))
            existing_cols = [row[1] for row in existing_cols_res.fetchall()]
            
            new_columns = {
                "subscriber_name": "VARCHAR(100)",
                "package_name": "VARCHAR(100)",
                "device_uid": "VARCHAR(100)",
                "session_cookies": "TEXT",
            }
            for col_name, col_type in new_columns.items():
                if col_name not in existing_cols:
                    await conn.execute(text(f"ALTER TABLE lines ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass

async def get_session():
    async with async_session() as session:
        yield session
