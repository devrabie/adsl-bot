import os
import logging
import datetime
from typing import List
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import async_session
from core.models import Line, Snapshot
from core.security import encrypt_password, decrypt_password
from services.scraper import YemenNetScraper, ScraperError
from services.excel_generator import generate_dsl_report_excel
from bot.keyboards.main_kb import (
    main_dashboard_kb,
    lines_list_kb,
    line_details_kb,
    cancel_fsm_kb,
    line_delete_confirm_kb,
    back_to_main_kb
)
from bot.states.line_states import AddLineSG, EditLineThresholdSG

router = Router()
logger = logging.getLogger(__name__)

def build_line_status_text(line: Line, net_24h: float = 0.0) -> str:
    if line.last_error:
        return f"🔴 <b>الخط {line.id} ({line.phone_number})</b>\n   └ ⚠️ <i>خطأ: {line.last_error}</i>"

    status_icon = "🟢"
    status_label = "مستقر"
    if line.remaining_gb < line.gb_threshold_critical or line.days_left < line.days_threshold_critical:
        status_icon = "🔴"
        status_label = "حرج"
    elif line.remaining_gb < line.gb_threshold_warning or line.days_left < line.days_threshold_warning:
        status_icon = "🟡"
        status_label = "تنبيه"

    return (
        f"{status_icon} <b>الخط {line.id} ({line.phone_number})</b> - [{status_label}]\n"
        f"   ├ 💳 الرصيد المتبقي: <b>{line.remaining_gb:.2f} GB</b> / {line.total_gb:.2f} GB\n"
        f"   ├ 📉 مستهلك 24 ساعة: <b>{net_24h:.2f} GB</b>\n"
        f"   ├ 📅 تاريخ الانتهاء: <b>{line.expiry_date}</b> ({line.days_left} يوم متبقي)\n"
        f"   └ 🕒 آخر تحديث: {line.last_scraped_at.strftime('%Y-%m-%d %H:%M') if line.last_scraped_at else 'غير محدد'}"
    )

async def calculate_24h_consumption(session: AsyncSession, line_id: int, current_rem_gb: float) -> float:
    stmt = select(Snapshot).where(Snapshot.line_id == line_id).order_by(Snapshot.created_at.desc()).limit(1)
    res = await session.execute(stmt)
    snap = res.scalar_one_or_none()
    if snap:
        consumption = snap.remaining_gb - current_rem_gb
        return max(0.0, round(consumption, 2))
    return 0.0

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "<b>👋 مرحباً بك في نظام مراقبة خطوط الإنترنت (يمن نت / تليمن)</b>\n\n"
        "يمكنك متابعة الاستهلاك، التنبيهات الفورية، وإصدار التقارير اليومية وملفات Excel بنقرة واحدة."
    )
    await message.answer(text, reply_markup=main_dashboard_kb(), parse_mode="HTML")

@router.callback_query(F.data == "btn_main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "<b>🏠 لوحة التحكم الرئيسية</b>\n\n"
        "اختر الخيار المطلوب من القائمة أدناه:"
    )
    await callback.message.edit_text(text, reply_markup=main_dashboard_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "btn_cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ تم إلغاء العملية.", reply_markup=back_to_main_kb())
    await callback.answer()

# --- Instant Report ---
@router.callback_query(F.data == "btn_instant_report")
async def cb_instant_report(callback: CallbackQuery):
    await callback.answer("⏳ جاري جلب تقرير الخطوط...")
    async with async_session() as session:
        stmt = select(Line).where(Line.is_active == True).order_by(Line.id.asc())
        res = await session.execute(stmt)
        lines = res.scalars().all()

        if not lines:
            await callback.message.edit_text("ℹ️ لا يوجد أي خطوط مضافة حالياً.", reply_markup=main_dashboard_kb())
            return

        report_lines = []
        total_remaining = 0.0
        total_24h = 0.0

        for line in lines:
            net_24h = await calculate_24h_consumption(session, line.id, line.remaining_gb)
            report_lines.append(build_line_status_text(line, net_24h))
            total_remaining += line.remaining_gb
            total_24h += net_24h

        full_text = (
            f"📊 <b>تقرير حالة الخطوط الحالية ({len(lines)} خط)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            + "\n\n".join(report_lines) +
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 إجمالي الرصيد المتبقي: <b>{total_remaining:.2f} GB</b>\n"
            f"📉 إجمالي الاستهلاك خلال 24 ساعة: <b>{total_24h:.2f} GB</b>"
        )
        await callback.message.edit_text(full_text, reply_markup=main_dashboard_kb(), parse_mode="HTML")

# --- Export Excel ---
@router.callback_query(F.data == "btn_export_excel")
async def cb_export_excel(callback: CallbackQuery):
    await callback.answer("⏳ جاري توليد ملف Excel...")
    async with async_session() as session:
        stmt = select(Line).where(Line.is_active == True).order_by(Line.id.asc())
        res = await session.execute(stmt)
        lines = res.scalars().all()

        if not lines:
            await callback.message.answer("ℹ️ لا يوجد خطوط لتصدير التقرير.")
            return

        export_data = []
        for line in lines:
            net_24h = await calculate_24h_consumption(session, line.id, line.remaining_gb)
            status_str = "مستقر"
            if line.remaining_gb < line.gb_threshold_critical or line.days_left < line.days_threshold_critical:
                status_str = "حرج"
            elif line.remaining_gb < line.gb_threshold_warning or line.days_left < line.days_threshold_warning:
                status_str = "تنبيه"

            export_data.append({
                "id": line.id,
                "phone_number": line.phone_number,
                "total_gb": line.total_gb,
                "used_gb": line.used_gb,
                "remaining_gb": line.remaining_gb,
                "net_consumption_24h": net_24h,
                "expiry_date": line.expiry_date or "-",
                "days_left": line.days_left,
                "status_str": status_str,
                "last_error": line.last_error
            })

        filename = f"dsl_report_{datetime.date.today().strftime('%Y_%m_%d')}.xlsx"
        filepath = os.path.join("/tmp", filename)
        generate_dsl_report_excel(export_data, filepath)

        excel_file = FSInputFile(filepath, filename=filename)
        await callback.message.answer_document(
            document=excel_file,
            caption="📊 <b>تفضل تقرير حالة الخطوط بملف Excel المنقح</b>",
            parse_mode="HTML"
        )
        if os.path.exists(filepath):
            os.remove(filepath)

# --- Sync All Lines ---
@router.callback_query(F.data == "btn_sync_all")
async def cb_sync_all(callback: CallbackQuery):
    await callback.answer("⏳ جاري تحديث بيانات كافة الخطوط من يمن نت...")
    scraper = YemenNetScraper()

    async with async_session() as session:
        stmt = select(Line).where(Line.is_active == True)
        res = await session.execute(stmt)
        lines = res.scalars().all()

        if not lines:
            await callback.message.answer("ℹ️ لا يوجد خطوط مضافة لتحديثها.")
            return

        updated_count = 0
        error_count = 0

        for line in lines:
            try:
                raw_password = decrypt_password(line.encrypted_password)
                data = await scraper.fetch_account_data(line.phone_number, raw_password)

                line.total_gb = data["total_gb"]
                line.used_gb = data["used_gb"]
                line.remaining_gb = data["remaining_gb"]
                line.expiry_date = data["expiry_date"]
                line.days_left = data["days_left"]
                line.last_scraped_at = datetime.datetime.utcnow()
                line.last_error = None

                if line.remaining_gb >= line.gb_threshold_warning:
                    line.alert_50gb_sent = False
                    line.alert_10gb_sent = False
                elif line.remaining_gb >= line.gb_threshold_critical:
                    line.alert_10gb_sent = False

                if line.days_left >= line.days_threshold_warning:
                    line.alert_10days_sent = False
                    line.alert_5days_sent = False
                elif line.days_left >= line.days_threshold_critical:
                    line.alert_5days_sent = False

                updated_count += 1
            except Exception as e:
                line.last_error = str(e)
                error_count += 1

        await session.commit()

    await callback.message.answer(
        f"✅ <b>اكتمال التحديث:</b>\n"
        f"├ 🟢 تم تحديث: {updated_count} خط بنجاح\n"
        f"└ 🔴 تعثر تحديث: {error_count} خط",
        parse_mode="HTML",
        reply_markup=main_dashboard_kb()
    )

# --- Line Management ---
@router.callback_query(F.data == "btn_manage_lines")
async def cb_manage_lines(callback: CallbackQuery):
    async with async_session() as session:
        stmt = select(Line).where(Line.is_active == True).order_by(Line.id.asc())
        res = await session.execute(stmt)
        lines = res.scalars().all()

        if not lines:
            await callback.message.edit_text(
                "⚙️ <b>إدارة الخطوط</b>\n\nلا يوجد أي خطوط مضافة حالياً. اضغط أدناه لإضافة خط جديد.",
                reply_markup=lines_list_kb([]),
                parse_mode="HTML"
            )
            return

        await callback.message.edit_text(
            "⚙️ <b>إدارة الخطوط المتاحة</b>\n\nاختر الخط لاستعراض التفاصيل والتعديل/الحذف:",
            reply_markup=lines_list_kb(lines),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("line_details:"))
async def cb_line_details(callback: CallbackQuery):
    line_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        line = await session.get(Line, line_id)
        if not line:
            await callback.answer("⚠️ هذا الخط غير موجود.", show_alert=True)
            return

        net_24h = await calculate_24h_consumption(session, line.id, line.remaining_gb)
        text = (
            f"📄 <b>تفاصيل الخط {line.id}</b>\n\n"
            f"{build_line_status_text(line, net_24h)}\n\n"
            f"<b>⚙️ إعدادات التنبيهات الحالية لهذا الخط:</b>\n"
            f"├ تنبيه الرصيد الأصفر: <b>{line.gb_threshold_warning} GB</b>\n"
            f"├ تنبيه الرصيد الأحمر: <b>{line.gb_threshold_critical} GB</b>\n"
            f"├ تنبيه الصلاحية الأصفر: <b>{line.days_threshold_warning} يوم</b>\n"
            f"└ تنبيه الصلاحية الأحمر: <b>{line.days_threshold_critical} يوم</b>"
        )
        await callback.message.edit_text(text, reply_markup=line_details_kb(line.id), parse_mode="HTML")

@router.callback_query(F.data.startswith("line_sync:"))
async def cb_line_sync(callback: CallbackQuery):
    line_id = int(callback.data.split(":")[1])
    await callback.answer("⏳ جاري فحص وتحديث هذا الخط...")

    scraper = YemenNetScraper()
    async with async_session() as session:
        line = await session.get(Line, line_id)
        if not line:
            await callback.answer("⚠️ هذا الخط غير موجود.", show_alert=True)
            return

        try:
            raw_password = decrypt_password(line.encrypted_password)
            data = await scraper.fetch_account_data(line.phone_number, raw_password)

            line.total_gb = data["total_gb"]
            line.used_gb = data["used_gb"]
            line.remaining_gb = data["remaining_gb"]
            line.expiry_date = data["expiry_date"]
            line.days_left = data["days_left"]
            line.last_scraped_at = datetime.datetime.utcnow()
            line.last_error = None

            await session.commit()
            await callback.message.answer(f"✅ تم تحديث بيانات الخط ({line.phone_number}) بنجاح!")
        except Exception as e:
            line.last_error = str(e)
            await session.commit()
            await callback.message.answer(f"❌ تعثر تحديث الخط ({line.phone_number}): {e}")

# --- Line Threshold Customization Flow ---
@router.callback_query(F.data.startswith("line_thresholds:"))
async def cb_line_thresholds_start(callback: CallbackQuery, state: FSMContext):
    line_id = int(callback.data.split(":")[1])
    await state.update_data(editing_line_id=line_id)
    await state.set_state(EditLineThresholdSG.waiting_for_gb_warning)
    await callback.message.edit_text(
        f"⚙️ <b>تخصيص عتبات التنبيه للخط {line_id}</b>\n\n"
        f"أدخل عتبة الرصيد الأصفر (GB) عند وصول الرصيد إليها أو دونها (مثال: 50):",
        reply_markup=cancel_fsm_kb(),
        parse_mode="HTML"
    )

@router.message(EditLineThresholdSG.waiting_for_gb_warning)
async def process_gb_warning(message: Message, state: FSMContext):
    val = message.text.strip()
    try:
        gb_warn = float(val)
        await state.update_data(gb_warning=gb_warn)
        await state.set_state(EditLineThresholdSG.waiting_for_gb_critical)
        await message.answer("أدخل عتبة الرصيد الأحمر الحرج (GB) (مثال: 10):", reply_markup=cancel_fsm_kb())
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح بوحدة الجيجابايت:", reply_markup=cancel_fsm_kb())

@router.message(EditLineThresholdSG.waiting_for_gb_critical)
async def process_gb_critical(message: Message, state: FSMContext):
    val = message.text.strip()
    try:
        gb_crit = float(val)
        await state.update_data(gb_critical=gb_crit)
        await state.set_state(EditLineThresholdSG.waiting_for_days_warning)
        await message.answer("أدخل عتبة الأيام المتبقية للتنبيه الأصفر (أيام) (مثال: 10):", reply_markup=cancel_fsm_kb())
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح بوحدة الجيجابايت:", reply_markup=cancel_fsm_kb())

@router.message(EditLineThresholdSG.waiting_for_days_warning)
async def process_days_warning(message: Message, state: FSMContext):
    val = message.text.strip()
    try:
        days_warn = int(val)
        await state.update_data(days_warning=days_warn)
        await state.set_state(EditLineThresholdSG.waiting_for_days_critical)
        await message.answer("أدخل عتبة الأيام المتبقية للتنبيه الأحمر الحرج (أيام) (مثال: 5):", reply_markup=cancel_fsm_kb())
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح للأيام:", reply_markup=cancel_fsm_kb())

@router.message(EditLineThresholdSG.waiting_for_days_critical)
async def process_days_critical(message: Message, state: FSMContext):
    val = message.text.strip()
    try:
        days_crit = int(val)
        data = await state.get_data()
        line_id = data["editing_line_id"]

        async with async_session() as session:
            line = await session.get(Line, line_id)
            if line:
                line.gb_threshold_warning = data["gb_warning"]
                line.gb_threshold_critical = data["gb_critical"]
                line.days_threshold_warning = data["days_warning"]
                line.days_threshold_critical = days_crit
                await session.commit()

        await state.clear()
        await message.answer(
            f"✅ <b>تم حفظ عتبات التنبيه الجديدة للخط {line_id} بنجاح!</b>",
            reply_markup=main_dashboard_kb(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح للأيام:", reply_markup=cancel_fsm_kb())

# --- Add Line FSM Flow ---
@router.callback_query(F.data == "btn_add_line")
async def cb_add_line_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddLineSG.waiting_for_phone)
    text = (
        "➕ <b>إضافة خط جديد</b>\n\n"
        "الرجاء إدخال رقم الهاتف الثابت الخاص بفرع الإنترنت (مثال: 01234567):"
    )
    await callback.message.edit_text(text, reply_markup=cancel_fsm_kb(), parse_mode="HTML")

@router.message(AddLineSG.waiting_for_phone)
async def process_add_phone(message: Message, state: FSMContext):
    phone_number = message.text.strip()
    if not phone_number.isdigit() or len(phone_number) < 6:
        await message.answer("⚠️ رقم الخط غير صحيح. يرجى إدخال رقم هاتف ثابت صحيح (أرقام فقط):", reply_markup=cancel_fsm_kb())
        return

    async with async_session() as session:
        stmt = select(Line).where(Line.phone_number == phone_number)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            await message.answer(f"⚠️ الرقم ({phone_number}) مضاف بالفعل في النظام!", reply_markup=cancel_fsm_kb())
            return

    await state.update_data(phone_number=phone_number)
    await state.set_state(AddLineSG.waiting_for_password)
    await message.answer("🔑 الآن، أدخل كلمة المرور الخاصة بهذا الخط في بوابة يمن نت:", reply_markup=cancel_fsm_kb())

@router.message(AddLineSG.waiting_for_password)
async def process_add_password(message: Message, state: FSMContext):
    password = message.text.strip()
    fsm_data = await state.get_data()
    phone_number = fsm_data["phone_number"]

    wait_msg = await message.answer("⏳ جاري القيام بفحص تجريبي فوري للتحقق من صحة رقم الخط وكلمة السر مع بوابة يمن نت...")

    scraper = YemenNetScraper()
    try:
        data = await scraper.fetch_account_data(phone_number, password)
        enc_pass = encrypt_password(password)
        async with async_session() as session:
            new_line = Line(
                phone_number=phone_number,
                encrypted_password=enc_pass,
                total_gb=data["total_gb"],
                used_gb=data["used_gb"],
                remaining_gb=data["remaining_gb"],
                expiry_date=data["expiry_date"],
                days_left=data["days_left"],
                last_scraped_at=datetime.datetime.utcnow(),
                last_error=None
            )
            session.add(new_line)
            await session.commit()
            await session.refresh(new_line)

            snap = Snapshot(
                line_id=new_line.id,
                total_gb=new_line.total_gb,
                used_gb=new_line.used_gb,
                remaining_gb=new_line.remaining_gb,
                days_left=new_line.days_left
            )
            session.add(snap)
            await session.commit()

            assigned_id = new_line.id

        await state.clear()
        await wait_msg.edit_text(
            f"🎉 <b>تم حفظ واختبار الخط بنجاح!</b>\n\n"
            f"📌 تم تعيين المعرف للخط تلقائياً: <b>الخط {assigned_id}</b> ({phone_number})\n"
            f"💳 الرصيد المتبقي: {data['remaining_gb']} GB\n"
            f"📅 الصلاحية: {data['days_left']} يوم",
            reply_markup=main_dashboard_kb(),
            parse_mode="HTML"
        )
    except ScraperError as e:
        await wait_msg.edit_text(
            f"❌ <b>فشل الفحص التجريبي:</b>\n{str(e)}\n\n"
            f"تأكد من صحة رقم الخط وكلمة المرور وحاول مرة أخرى.",
            reply_markup=cancel_fsm_kb(),
            parse_mode="HTML"
        )

# --- Delete Line Flow ---
@router.callback_query(F.data.startswith("line_delete_confirm:"))
async def cb_delete_confirm(callback: CallbackQuery):
    line_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"⚠️ <b>هل أنت أکید من رغبتك في حذف الخط {line_id} نهائياً؟</b>",
        reply_markup=line_delete_confirm_kb(line_id),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("line_delete_execute:"))
async def cb_delete_execute(callback: CallbackQuery):
    line_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        stmt = delete(Line).where(Line.id == line_id)
        await session.execute(stmt)
        await session.commit()

    await callback.message.edit_text(f"🗑️ تم حذف الخط {line_id} بنجاح من قاعدة البيانات.", reply_markup=back_to_main_kb())

# --- Settings ---
@router.callback_query(F.data == "btn_settings")
async def cb_settings(callback: CallbackQuery):
    text = (
        "⚙️ <b>إعدادات النظام والتنبيهات</b>\n\n"
        "├ زمن الفحص الدوري: كل 4 ساعات\n"
        "├ موعد التقرير اليومي: الساعة 21:00 (توقيت عدن)\n"
        "└ العتبات المفتراضية للتنبيه:\n"
        "   - الرصيد الأصفر: 50 GB | الأحمر: 10 GB\n"
        "   - الصلاحية الأصفر: 10 أيام | الأحمر: 5 أيام\n\n"
        "💡 يمكنك تخصيص العتبات لكل خط على حدة من قائمة 'إدارة الخطوط'."
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb(), parse_mode="HTML")
