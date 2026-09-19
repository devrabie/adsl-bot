from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from core.config import settings

class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        allowed_ids = settings.admins_list

        if user_id and user_id in allowed_ids:
            return await handler(event, data)

        # Reject unauthorized users strictly
        if isinstance(event, Message):
            await event.answer("⚠️ عذراً، لا تملك الصلاحيات لاستخدام هذا البوت.")
        elif isinstance(event, CallbackQuery):
            await event.answer("⚠️ غير مصرح لك لاستخدام هذا البوت.", show_alert=True)

        return
