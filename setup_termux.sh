#!/data/data/com.termux/files/usr/bin/bash

# ==========================================================
#  YemenNet ADSL Monitor Bot - Termux Auto Installer
# ==========================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN}   [+] YemenNet ADSL Bot Installer for Termux       ${NC}"
echo -e "${CYAN}====================================================${NC}"

# 0. Telegram Credentials Prompt
echo -e "\n${YELLOW}[Setup] Please enter your Telegram Bot credentials:${NC}"

while true; do
    read -p ">> Enter Bot Token: " BOT_TOKEN
    if [ -n "$BOT_TOKEN" ]; then
        break
    else
        echo -e "${RED}[!] Bot Token cannot be empty!${NC}"
    fi
done

while true; do
    read -p ">> Enter Admin Telegram ID: " ADMIN_ID
    if [ -n "$ADMIN_ID" ]; then
        break
    else
        echo -e "${RED}[!] Admin ID cannot be empty!${NC}"
    fi
done

# 1. Update Termux repositories
echo -e "\n${YELLOW}[1/5] Updating Termux packages...${NC}"
pkg update -y

# 2. Install prebuilt system packages and Rust compiler tools
echo -e "\n${YELLOW}[2/5] Installing Python, Rust & dependencies...${NC}"
pkg install -y python git clang rust binutils libffi openssl libxml2 libxslt libjpeg-turbo freetype termux-api python-cryptography

# Resolve Python shared library path dynamically and export to LD_PRELOAD
PY_SO=$(find "$PREFIX/lib" -maxdepth 1 -name "libpython3.*.so" | head -n 1)
if [ -n "$PY_SO" ]; then
    export LD_PRELOAD="$PY_SO"
fi

# 3. Setup Virtual Environment linked with system packages
echo -e "\n${YELLOW}[3/5] Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python -m venv --system-site-packages venv
fi

# Ensure all binaries in venv have executable permissions
chmod +x ./venv/bin/* 2>/dev/null || true

source venv/bin/activate
pip install --upgrade pip setuptools wheel maturin

# 4. Install requirements, tzdata for Aden timezone & Arabic text tools
echo -e "\n${YELLOW}[4/5] Installing project Python requirements...${NC}"
pip install tzdata arabic-reshaper
pip install --no-build-isolation python-bidi || true
pip install --no-build-isolation -r requirements.txt

# 5. Generate Fernet Key and write .env
echo -e "\n${YELLOW}[5/5] Writing configuration to .env...${NC}"
FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

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
echo -e "${GREEN}[OK] .env configuration generated!${NC}"

# Database Initialization
echo -e "\n${YELLOW}[*] Initializing local database...${NC}"
python -c "import asyncio; from core.db import init_db; asyncio.run(init_db())"
echo -e "${GREEN}[OK] Database initialized successfully!${NC}"

# Ensure start script has executable rights
chmod +x start_termux.sh 2>/dev/null || true

echo -e "\n${CYAN}====================================================${NC}"
echo -e "${GREEN}[SUCCESS] Installation finished!${NC}"
echo -e "${CYAN}Start the bot anytime using:${NC}"
echo -e "   ${YELLOW}./start_termux.sh${NC}"
echo -e "${CYAN}====================================================${NC}\n"
