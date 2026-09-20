import os
import tempfile
import logging
import datetime
import pytz
from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.db import async_session
from core.models import Line, Snapshot
from core.security import decrypt_password
from services.scraper import YemenNetScraper, CaptchaRequiredError
from services.excel_generator import generate_dsl_report_excel
from bot.handlers.main_handler import build_line_status_text, calculate_24h_consumption

logger = logging.getLogger(__name__)

async def run_daily_report_job(bot: Bot):
    """
    Daily scheduled job (e.g. 21:00 Aden time):
    1. Scrapes all active lines using saved session cookies.
    2. Computes 24h net consumption comparing with prior snapshot.
    3. Saves new daily balance snapshot.
    4. Generates dual report: HTML Telegram message + Excel file.
    5. Sends report to all ADMINS_ID.
    """
    logger.info("Starting scheduled daily report job...")
    scraper = YemenNetScraper()

    async with async_session() as session:
        stmt = select(Line).where(Line.is_active == True).order_by(Line.id.asc())
        res = await session.execute(stmt)
        lines = res.scalars().all()

        if not lines:
            logger.info("No active lines found for daily report job.")
            return

        report_data_for_excel = []
        msg_lines = []
        total_remaining = 0.0
        total_24h = 0.0

        for line in lines:
            try:
                raw_pass = decrypt_password(line.encrypted_password)
                data, updated_cookies = await scraper.fetch_account_data(
                    line.phone_number,
                    raw_pass,
                    session_cookies=line.session_cookies,
                    device_uid=line.device_uid
                )

                line.subscriber_name = data.get("subscriber_name") or line.subscriber_name
                line.package_name = data.get("package_name") or line.package_name
                line.session_cookies = updated_cookies
                line.total_gb = data["total_gb"]
                line.used_gb = data["used_gb"]
                line.remaining_gb = data["remaining_gb"]
                line.expiry_date = data["expiry_date"]
                line.days_left = data["days_left"]
                line.last_scraped_at = datetime.datetime.utcnow()
                line.last_error = None
            except CaptchaRequiredError:
                line.last_error = "انتهت الجلسة، يلزم تجديد الكباتشا من البوت"
                logger.warning(f"Session expired for line {line.phone_number}, needs captcha.")
            except Exception as e:
                line.last_error = str(e)
                logger.error(f"Error scraping line {line.phone_number} in daily job: {e}")

            # Calculate 24h consumption BEFORE adding new snapshot to session
            net_24h = await calculate_24h_consumption(session, line.id, line.remaining_gb)

            # Create daily Snapshot if no error or if we have valid data
            if not line.last_error or line.remaining_gb > 0:
                snap = Snapshot(
                    line_id=line.id,
                    total_gb=line.total_gb,
                    used_gb=line.used_gb,
                    remaining_gb=line.remaining_gb,
                    days_left=line.days_left,
                    created_at=datetime.datetime.utcnow()
                )
                session.add(snap)

            msg_lines.append(build_line_status_text(line, net_24h))

            total_remaining += line.remaining_gb
            total_24h += net_24h

            status_str = "مستقر"
            if line.remaining_gb < line.gb_threshold_critical or line.days_left < line.days_threshold_critical:
                status_str = "حرج"
            elif line.remaining_gb < line.gb_threshold_warning or line.days_left < line.days_threshold_warning:
                status_str = "تنبيه"

            report_data_for_excel.append({
                "id": line.id,
                "phone_number": line.phone_number,
                "subscriber_name": line.subscriber_name,
                "package_name": line.package_name,
                "total_gb": line.total_gb,
                "used_gb": line.used_gb,
                "remaining_gb": line.remaining_gb,
                "net_consumption_24h": net_24h,
                "expiry_date": line.expiry_date or "-",
                "days_left": line.days_left,
                "status_str": status_str,
                "last_error": line.last_error
            })

        await session.commit()

        # Build Excel report
        filename = f"daily_dsl_report_{datetime.date.today().strftime('%Y_%m_%d')}.xlsx"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        generate_dsl_report_excel(report_data_for_excel, filepath)

        full_message_text = (
            f"📅 <b>التقرير اليومي لمراقبة خطوط الإنترنت</b>\n"
            f"تاريخ: {datetime.date.today().strftime('%Y-%m-%d')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            + "\n\n".join(msg_lines) +
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 إجمالي الرصيد المتبقي: <b>{total_remaining:.2f} GB</b>\n"
            f"📉 إجمالي الاستهلاك الصافي خلال 24 ساعة: <b>{total_24h:.2f} GB</b>"
        )

        excel_file = FSInputFile(filepath, filename=filename)

        # Broadcast to all admins
        for admin_id in settings.admins_list:
            try:
                await bot.send_message(chat_id=admin_id, text=full_message_text, parse_mode="HTML")
                await bot.send_document(
                    chat_id=admin_id,
                    document=excel_file,
                    caption="📊 <b>ملف Excel للتقرير اليومي المنسق</b>",
                    parse_mode="HTML"
                )
            except Exception as admin_err:
                logger.error(f"Failed sending daily report to admin {admin_id}: {admin_err}")

        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

async def run_periodic_check_job(bot: Bot):
    """
    Fast periodic check job (e.g. every X hours):
    1. Scrapes all active lines using saved session cookies.
    2. Compares against custom alert thresholds.
    3. Sends Instant Alerts for 50GB, 10GB, 10 days, 5 days with deduplication (alert_sent flags).
    4. Auto-resets alert_sent flags when recharged above thresholds.
    """
    logger.info("Starting periodic check job for instant alerts...")
    scraper = YemenNetScraper()

    async with async_session() as session:
        stmt = select(Line).where(Line.is_active == True)
        res = await session.execute(stmt)
        lines = res.scalars().all()

        for line in lines:
            try:
                raw_pass = decrypt_password(line.encrypted_password)
                data, updated_cookies = await scraper.fetch_account_data(
                    line.phone_number,
                    raw_pass,
                    session_cookies=line.session_cookies,
                    device_uid=line.device_uid
                )

                line.subscriber_name = data.get("subscriber_name") or line.subscriber_name
                line.package_name = data.get("package_name") or line.package_name
                line.session_cookies = updated_cookies
                line.total_gb = data["total_gb"]
                line.used_gb = data["used_gb"]
                line.remaining_gb = data["remaining_gb"]
                line.expiry_date = data["expiry_date"]
                line.days_left = data["days_left"]
                line.last_scraped_at = datetime.datetime.utcnow()
                line.last_error = None
            except CaptchaRequiredError:
                line.last_error = "انتهت الجلسة، يلزم تجديد الكباتشا من البوت"
                # Send notice to admin once
                if not getattr(line, "alert_session_expired", False):
                    for admin_id in settings.admins_list:
                        try:
                            await bot.send_message(
                                chat_id=admin_id,
                                text=(
                                    f"⚠️ <b>تنبيه: انتهت جلسة الخط {line.phone_number}!</b>\n"
                                    f"يرجى الدخول للبوت وتجديد الجلسة عبر حل الكباتشا لاستمرار المراقبة التلقائية."
                                ),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                continue
            except Exception as e:
                line.last_error = str(e)
                continue

            alerts_to_send = []
            sub_info = f" ({line.subscriber_name})" if line.subscriber_name else ""

            # Check Critical GB Threshold (e.g. < 10GB)
            if line.remaining_gb <= line.gb_threshold_critical:
                if not line.alert_10gb_sent:
                    alerts_to_send.append(
                        f"🚨 <b>تنبيه حرج (الرصيد منخفض جداً)!</b>\n"
                        f"الخط {line.id} ({line.phone_number}){sub_info}\n"
                        f"الرصيد المتبقي وصل إلى <b>{line.remaining_gb:.2f} GB</b> (أقل من {line.gb_threshold_critical} GB)."
                    )
                    line.alert_10gb_sent = True
                    line.alert_50gb_sent = True
            # Check Warning GB Threshold (e.g. < 50GB)
            elif line.remaining_gb <= line.gb_threshold_warning:
                if not line.alert_50gb_sent:
                    alerts_to_send.append(
                        f"⚠️ <b>تنبيه تحذيري (انخفاض الرصيد)!</b>\n"
                        f"الخط {line.id} ({line.phone_number}){sub_info}\n"
                        f"الرصيد المتبقي وصل إلى <b>{line.remaining_gb:.2f} GB</b> (أقل من {line.gb_threshold_warning} GB)."
                    )
                    line.alert_50gb_sent = True
            else:
                # Auto-reset flags when recharged above warning threshold
                line.alert_50gb_sent = False
                line.alert_10gb_sent = False

            # Check Critical Days Threshold (e.g. < 5 days)
            if line.days_left <= line.days_threshold_critical:
                if not line.alert_5days_sent:
                    alerts_to_send.append(
                        f"🚨 <b>تنبيه حرج (اقتراب انتهاء الصلاحية)!</b>\n"
                        f"الخط {line.id} ({line.phone_number}){sub_info}\n"
                        f"الأيام المتبقية وصلت إلى <b>{line.days_left} يوم</b> (أقل من {line.days_threshold_critical} أيام)."
                    )
                    line.alert_5days_sent = True
                    line.alert_10days_sent = True
            # Check Warning Days Threshold (e.g. < 10 days)
            elif line.days_left <= line.days_threshold_warning:
                if not line.alert_10days_sent:
                    alerts_to_send.append(
                        f"⚠️ <b>تنبيه تحذيري (اقتراب انتهاء الصلاحية)!</b>\n"
                        f"الخط {line.id} ({line.phone_number}){sub_info}\n"
                        f"الأيام المتبقية وصلت إلى <b>{line.days_left} يوم</b> (أقل من {line.days_threshold_warning} أيام)."
                    )
                    line.alert_10days_sent = True
            else:
                # Auto-reset flags when extended
                line.alert_10days_sent = False
                line.alert_5days_sent = False

            # Send accumulated alerts for this line to admins
            for alert_text in alerts_to_send:
                for admin_id in settings.admins_list:
                    try:
                        await bot.send_message(chat_id=admin_id, text=alert_text, parse_mode="HTML")
                    except Exception as err:
                        logger.error(f"Failed sending instant alert to admin {admin_id}: {err}")

        await session.commit()

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    tz = pytz.timezone(settings.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    hour, minute = map(int, settings.REPORT_TIME.split(":"))

    # Daily Report Job
    scheduler.add_job(
        run_daily_report_job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[bot],
        id="daily_dsl_report_job",
        replace_existing=True
    )

    # Fast Periodic Check Job
    scheduler.add_job(
        run_periodic_check_job,
        trigger=IntervalTrigger(hours=settings.CHECK_INTERVAL_HOURS, timezone=tz),
        args=[bot],
        id="periodic_dsl_check_job",
        replace_existing=True
    )

    return scheduler
