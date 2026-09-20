#!/data/data/com.termux/files/usr/bin/bash

# ==========================================================
#  YemenNet ADSL Monitor Bot - Termux Auto Installer
#  تثبيت وتشغيل بوت مراقبة خطوط يمن نت على تطبيق Termux
# ==========================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN}   🤖 بدء تثبيت بوت مراقبة خطوط يمن نت ADSL على Termux${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. تحديث مستودعات تيرمكس
echo -e "\n${YELLOW}[1/5] تحديث حزم النظام في Termux...${NC}"
pkg update -y && pkg upgrade -y

# 2. تثبيت الحزم والمترجمات اللازمة
echo -e "\n${YELLOW}[2/5] تثبيت Python والحزم المساعدة والمكتبات...${NC}"
pkg install -y python git clang libffi openssl libxml2 libxslt libjpeg-turbo freetype termux-api

# 3. إعداد البيئة الافتراضية
echo -e "\n${YELLOW}[3/5] إنشاء البيئة الافتراضية للبايثون...${NC}"
if [ ! -d "venv" ]; then
    python -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip setuptools wheel

# 4. تثبيت متطلبات المشروع
echo -e "\n${YELLOW}[4/5] تثبيت مكتبات بايثون المطلوبة (قد يستغرق بضع دقائق)...${NC}"
pip install -r requirements.txt

# 5. إعداد ملف البيئة .env
echo -e "\n${YELLOW}[5/5] إعداد ملف الإعدادات (.env)...${NC}"
if [ ! -f ".env" ]; then
    # توليد مفتاح التشفير Fernet
    FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    echo -e "${CYAN}يرجى إدخال إعدادات البوت (أو اضغط Enter للاعتماد الافتراضي):${NC}"
    
    read -p "توكن البوت (Bot Token) [8462164343:AAGljKn7vEiH4Wq39nTDFC3x0BIlSB1teXE]: " INPUT_TOKEN
    BOT_TOKEN=${INPUT_TOKEN:-"8462164343:AAGljKn7vEiH4Wq39nTDFC3x0BIlSB1teXE"}

    read -p "معرف التيليجرام للأدمن (Admin ID) [6198033039]: " INPUT_ADMIN
    ADMIN_ID=${INPUT_ADMIN:-"6198033039"}

    cat <<EOF > .env
# Telegram Bot Configuration
BOT_TOKEN=${BOT_TOKEN}

# Admins Whitelist (comma-separated Telegram User IDs)
ADMINS_ID=${ADMIN_ID}

# Cryptography Fernet Key for encrypting passwords in DB
ENCRYPTION_KEY=${FERNET_KEY}

# Scheduler Settings
REPORT_TIME=21:00
TIMEZONE=Asia/Aden
CHECK_INTERVAL_HOURS=4

# Database URL
DATABASE_URL=sqlite+aiosqlite:///yemennet_dsl.db
EOF
    echo -e "${GREEN}✅ تم إنشاء ملف .env بنجاح!${NC}"
else
    echo -e "${GREEN}ℹ️ ملف .env موجود بالفعل، تم تخطي الإنشاء.${NC}"
fi

# تهيئة قاعدة البيانات
echo -e "\n${YELLOW}🛠️ تهيئة قاعدة البيانات...${NC}"
python -c "import asyncio; from core.db import init_db; asyncio.run(init_db())"
echo -e "${GREEN}✅ تم تجهيز قاعدة البيانات بنجاح!${NC}"

# إعطاء صلاحيات التشغيل لملف start_termux.sh
chmod +x start_termux.sh || true

echo -e "\n${CYAN}====================================================${NC}"
echo -e "${GREEN}🎉 تم الانتهاء من التثبيت بنجاح!${NC}"
echo -e "${CYAN}للتشغيل في أي وقت اكتب:${NC}"
echo -e "   ${YELLOW}./start_termux.sh${NC}"
echo -e "${CYAN}====================================================${NC}\n"
