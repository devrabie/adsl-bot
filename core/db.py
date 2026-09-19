from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings
from core.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session():
    async with async_session() as session:
        yield session
