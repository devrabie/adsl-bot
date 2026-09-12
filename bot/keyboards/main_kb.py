from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
from core.models import Line

def main_dashboard_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 تقرير فوري (شامل)", callback_data="btn_instant_report"),
            InlineKeyboardButton(text="📁 تصدير Excel", callback_data="btn_export_excel")
        ],
        [
            InlineKeyboardButton(text="⚙️ إدارة الخطوط", callback_data="btn_manage_lines"),
            InlineKeyboardButton(text="➕ إضافة خط جديد", callback_data="btn_add_line")
        ],
        [
            InlineKeyboardButton(text="🔄 تحديث البيانات للجميع", callback_data="btn_sync_all"),
            InlineKeyboardButton(text="⚙️ الإعدادات التلقائية", callback_data="btn_settings")
        ]
    ])
    return kb

def lines_list_kb(lines: List[Line]) -> InlineKeyboardMarkup:
    buttons = []
    for line in lines:
        status_icon = "🟢"
        if line.last_error:
            status_icon = "🔴"
        elif line.remaining_gb < line.gb_threshold_critical or line.days_left < line.days_threshold_critical:
            status_icon = "🔴"
        elif line.remaining_gb < line.gb_threshold_warning or line.days_left < line.days_threshold_warning:
            status_icon = "🟡"

        btn_text = f"{status_icon} الخط {line.id} ({line.phone_number})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"line_details:{line.id}")])

    buttons.append([InlineKeyboardButton(text="➕ إضافة خط جديد", callback_data="btn_add_line")])
    buttons.append([InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="btn_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def line_details_kb(line_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 تحديث الخط الآن", callback_data=f"line_sync:{line_id}"),
            InlineKeyboardButton(text="⚙️ تخصيص التنبيهات", callback_data=f"line_thresholds:{line_id}")
        ],
        [
            InlineKeyboardButton(text="🗑️ حذف الخط", callback_data=f"line_delete_confirm:{line_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 قائمة الخطوط", callback_data="btn_manage_lines"),
            InlineKeyboardButton(text="🏠 الرئيسية", callback_data="btn_main_menu")
        ]
    ])
    return kb

def cancel_fsm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء العملية", callback_data="btn_cancel_fsm")]
    ])

def line_delete_confirm_kb(line_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تأكيد الحذف النهائى", callback_data=f"line_delete_execute:{line_id}"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data=f"line_details:{line_id}")
        ]
    ])

def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="btn_main_menu")]
    ])
