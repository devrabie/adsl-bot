#!/data/data/com.termux/files/usr/bin/bash

# ==========================================================
#  YemenNet ADSL Monitor Bot - Termux Runner
# ==========================================================

# Preload Python runtime library to avoid Rust dlopen PyBaseObject_Type error
if [ -f "$PREFIX/lib/libpython3.13.so" ]; then
    export LD_PRELOAD=$PREFIX/lib/libpython3.13.so
fi

# Acquire Termux Wake-Lock to prevent Android from killing the bot in background
if command -v termux-wake-lock >/dev/null 2>&1; then
    echo "[*] Enabling Wake Lock for background running..."
    termux-wake-lock 2>/dev/null || true
fi

# Activate Virtual Environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Cleanup handler on stop/exit
cleanup() {
    echo -e "\n[!] Stopping bot..."
    if command -v termux-wake-unlock >/dev/null 2>&1; then
        termux-wake-unlock 2>/dev/null || true
        echo "[*] Wake Lock released."
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "[>] Starting Yemen Net DSL Monitor Bot..."
python main.py

cleanup
