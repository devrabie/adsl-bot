import os
import asyncio
import datetime
from aiogram import Bot, Dispatcher
from core.config import settings
from core.db import init_db
from bot.middlewares.whitelist import WhitelistMiddleware
from bot.handlers.main_handler import router as main_router
from services.scheduler import setup_scheduler

async def main():
    print("🚀 Starting Yemen Net DSL Monitor Bot...")

    # Initialize DB tables
    await init_db()
    print("✅ Database initialized successfully.")

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Register Middlewares
    dp.message.outer_middleware(WhitelistMiddleware())
    dp.callback_query.outer_middleware(WhitelistMiddleware())

    # Register Routers
    dp.include_router(main_router)

    # Setup Scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    print("⏰ Scheduler started successfully.")

    print(f"🤖 Bot active for Admins: {settings.admins_list}")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
