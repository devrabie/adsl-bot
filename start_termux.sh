#!/data/data/com.termux/files/usr/bin/bash

# ==========================================================
#  YemenNet ADSL Monitor Bot - Termux Runner
# ==========================================================

# منع نظام الأندرويد من إيقاف التطبيق عند قفل الشاشة
if command -v termux-wake-lock >/dev/null 2>&1; then
    echo "🔒 تفعيل قفل الاستيقاظ (Wake Lock) لضمان استمرار البوت في الخلفية..."
    termux-wake-lock
fi

# تفعيل البيئة الافتراضية
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# دالة التعامل مع الإغلاق
cleanup() {
    echo -e "\n🛑 يتم الآن إيقاف البوت..."
    if command -v termux-wake-unlock >/dev/null 2>&1; then
        termux-wake-unlock
        echo "🔓 تم فك قفل الاستيقاظ (Wake Lock)."
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🚀 جاري تشغيل بوت مراقبة خطوط يمن نت..."
python main.py

cleanup
