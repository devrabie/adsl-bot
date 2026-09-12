# Yemen Net DSL Monitor Bot (يمن نت / تليمن)

مشروع متكامل ومحترف لبوت تليجرام بلغة **Python** لمراقبة وإدارة خطوط الإنترنت المنزلي والتجاري (ADSL) الخاصة بمزود الخدمة (يمن نت / تليمن).

## 🌟 الميزات الرئيسية

- **التحكم والوصول الصارم (Whitelist):** حظر أي مستخدم غير مصرح له تلقائياً بناءً على قائمة `ADMINS_ID`.
- **التشفير القوي:** تشفير كلمات مرور الحسابات المخزنة في قاعدة البيانات باستخدام مكتبة `cryptography` (تشفير Fernet).
- **كشط البيانات التلقائي (Scraper Module):** خدمة غير متزامنة مع آليات إعادة المحاولة لسحب الرصيد الإجمالي، المستهلك، المتبقي (GB)، وتاريخ الانتهاء والأيام المتبقية.
- **إدارة الخطوط (FSM):** إضافة وتعديل وحذف الخطوط مع فحص فوري تجريبي لصحة البيانات قبل الحفظ.
- **التقارير المجدولة:** تقرير يومي مجدول (الساعة 9:00 مساءً) يتضمن ملخص نصي في تليجرام + ملف **Excel** احترافي منسق (RTL).
- **التنبيهات الفورية (Instant Alerts):** تنبيهات عند انخفاض الرصيد (50GB و 10GB) أو قرب انتهاء الصلاحية (10 أيام و 5 أيام) مع آلية إعادة التعيين التلقائية عند الشحن.

---

## 🛠️ التثبيت والتشغيل المحلي

### 1. استكشاف المشروع وإعداد البيئة

```bash
git clone <repository_url>
cd yemennet-dsl-monitor

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. إعداد ملف البيئة `.env`

قم بإنشاء ملف `.env` بناءً على `.env.example`:

```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMINS_ID=123456789,987654321
ENCRYPTION_KEY=your_fernet_key_here
REPORT_TIME=21:00
TIMEZONE=Asia/Aden
CHECK_INTERVAL_HOURS=4
DATABASE_URL=sqlite+aiosqlite:///yemennet_dsl.db
```

لإنشاء مفتاح تشفير `ENCRYPTION_KEY` جديد:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. تشغيل البوت

```bash
python main.py
```

---

## 🚀 التشغيل كـ الخدمة (systemd)

قم بإنشاء ملف `/etc/systemd/system/yemennet-dsl-bot.service`:

```ini
[Unit]
Description=YemenNet DSL Monitor Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/yemennet-dsl-monitor
ExecStart=/path/to/yemennet-dsl-monitor/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

ثم قم بتفعيل الخدمة وتشغيلها:
```bash
sudo systemctl daemon-reload
sudo systemctl enable yemennet-dsl-bot
sudo systemctl start yemennet-dsl-bot
```

---

## 🐳 التشغيل عبر Docker & Docker Compose

### 1. باستخدام Docker Compose

```bash
docker-compose up -d --build
```

---

## 🧪 إجراء الاختبارات (Testing)

```bash
PYTHONPATH=. pytest tests/
```
