import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User, Chat
from bot.middlewares.whitelist import WhitelistMiddleware
from core.config import settings

class DummyHandler:
    async def __call__(self, event, data):
        return "allowed"

@pytest.mark.asyncio
async def test_whitelist_middleware_allowed():
    middleware = WhitelistMiddleware()
    admin_id = settings.admins_list[0]

    message = MagicMock(spec=Message)
    message.from_user = User(id=admin_id, is_bot=False, first_name="Admin")

    handler = DummyHandler()
    res = await middleware(handler, message, {})
    assert res == "allowed"

@pytest.mark.asyncio
async def test_whitelist_middleware_denied():
    middleware = WhitelistMiddleware()
    unauthorized_id = 999999999

    message = MagicMock(spec=Message)
    message.from_user = User(id=unauthorized_id, is_bot=False, first_name="Hacker")
    message.answer = AsyncMock()

    handler = DummyHandler()
    res = await middleware(handler, message, {})
    assert res is None
    message.answer.assert_called_once()
