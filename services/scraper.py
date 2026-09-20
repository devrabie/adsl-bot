import re
import json
import uuid
import logging
import datetime
from typing import Dict, Any, Optional, Tuple, List
import httpx
import pytz
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://adsl.yemen.net.ye"
LOGIN_URL = f"{BASE_URL}/login"
CAPTCHA_URL = f"{BASE_URL}/captcha"
ACCT_URL = f"{BASE_URL}/acct"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ar,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

class ScraperError(Exception):
    """Custom exception for scraper failures."""
    pass

class CaptchaRequiredError(ScraperError):
    """Raised when captcha is required to complete authentication."""
    def __init__(self, message: str, session_state: dict, captcha_bytes: bytes):
        super().__init__(message)
        self.session_state = session_state
        self.captcha_bytes = captcha_bytes

class SessionExpiredError(ScraperError):
    """Raised when an existing session is expired."""
    pass

def normalize_arabic_numbers(text: str) -> str:
    if not text:
        return ""
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    trans = str.maketrans(arabic_digits, english_digits)
    text = text.translate(trans)
    # Replace Arabic decimal comma ٫ with standard dot .
    text = text.replace('٫', '.')
    # Strip invisible directional unicode markers
    text = text.replace('\u200f', '').replace('\u200e', '').replace('\u060f', '')
    return text.strip()

def _extract_safeline_array(var_name: str, text: str) -> Optional[bytes]:
    pattern = rf'{var_name}\s*=\s*(?:new\s+Uint8Array\s*\(\s*)?(\[[^\]]+\])'
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        arr = json.loads(m.group(1))
        return bytes(arr)
    except Exception:
        return None

def decrypt_safeline_waf(html: str) -> str:
    """Decrypts SafeLine WAF AES-GCM challenge if present."""
    if "Protected By" not in html and "AES-GCM" not in html:
        return html
    try:
        raw_key = _extract_safeline_array('raw_key', html)
        iv = _extract_safeline_array('iv', html)
        tag = _extract_safeline_array('tag', html)
        encrypted = _extract_safeline_array('encrypted', html)
        if raw_key and iv and tag and encrypted:
            aesgcm = AESGCM(raw_key)
            decrypted = aesgcm.decrypt(iv, encrypted + tag, None)
            return decrypted.decode('utf-8', errors='replace')
    except Exception as e:
        logger.debug(f"WAF decryption note: {e}")
    return html

class YemenNetScraper:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def _create_client(self, cookies: Optional[List[Dict[str, str]]] = None) -> httpx.AsyncClient:
        kwargs: Dict[str, Any] = {
            "headers": DEFAULT_HEADERS,
            "timeout": self.timeout,
            "verify": False,
            "follow_redirects": True
        }
        if settings.HTTP_PROXY:
            kwargs["proxy"] = settings.HTTP_PROXY
        client = httpx.AsyncClient(**kwargs)
        if cookies:
            for c in cookies:
                client.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))
        return client

    def _serialize_cookies(self, client: httpx.AsyncClient) -> str:
        cookie_list = [
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
            for c in client.cookies.jar
        ]
        return json.dumps(cookie_list)

    def _parse_acct_page(self, html: str, phone_number: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')

        subscriber_name = "غير محدد"
        if soup.title and soup.title.string:
            title_clean = normalize_arabic_numbers(soup.title.string.strip())
            if "-" in title_clean:
                subscriber_name = title_clean.split("-", 1)[1].strip()
            else:
                subscriber_name = title_clean

        data_map: Dict[str, str] = {}
        for tr in soup.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            if len(cells) >= 2:
                key = cells[0].get_text().strip()
                val = normalize_arabic_numbers(cells[1].get_text().strip())
                data_map[key] = val

        parsed_phone = data_map.get("رقم الهاتف", phone_number)
        package_name = data_map.get("باقة الاشتراك", "باقة سوبرنت")
        status = data_map.get("حالة الاشتراك", "حساب نشط")

        # Balance (Remaining GB)
        raw_balance = data_map.get("الرصيد الحالي", "0")
        m_bal = re.search(r'([\d\.]+)', raw_balance)
        remaining_gb = float(m_bal.group(1)) if m_bal else 0.0

        # Package total GB
        m_pkg = re.search(r'\((\d+)\)', package_name)
        total_gb = float(m_pkg.group(1)) if m_pkg else 0.0
        if total_gb == 0.0:
            m_pkg2 = re.search(r'(\d+)\s*(?:جيجا|GB)', package_name, re.IGNORECASE)
            if m_pkg2:
                total_gb = float(m_pkg2.group(1))

        used_gb = round(max(0.0, total_gb - remaining_gb), 2) if total_gb > 0 else 0.0

        # Expiry Date & Days Left
        raw_expiry = data_map.get("تاريخ انتهاء الصلاحية", "")
        expiry_date = raw_expiry
        days_left = 0

        m_date = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', raw_expiry)
        if m_date:
            d, m, y = map(int, m_date.groups())
            tz = pytz.timezone("Asia/Aden")
            now_yemen = datetime.datetime.now(tz)
            expiry_dt = tz.localize(datetime.datetime(y, m, d, 23, 59, 59))
            delta = expiry_dt - now_yemen
            days_left = max(0, delta.days)
            expiry_date = f"{y:04d}-{m:02d}-{d:02d}"

        return {
            "subscriber_name": subscriber_name,
            "phone_number": parsed_phone,
            "package_name": package_name,
            "status": status,
            "total_gb": total_gb,
            "used_gb": used_gb,
            "remaining_gb": remaining_gb,
            "expiry_date": expiry_date,
            "days_left": days_left
        }

    async def fetch_with_session(self, cookies_json: str, device_uid: str) -> Optional[Tuple[Dict[str, Any], str]]:
        """
        Attempts to fetch live account usage using saved session cookies without captcha.
        Returns (parsed_dict, updated_cookies_json) if session is valid, or None if expired.
        """
        try:
            cookies = json.loads(cookies_json) if isinstance(cookies_json, str) else cookies_json
        except Exception:
            return None

        async with self._create_client(cookies) as client:
            try:
                res = await client.get(ACCT_URL)
                html = decrypt_safeline_waf(res.text)
                
                # Check if we landed on the account page
                if "بيانات الاشتراك" in html or "الرصيد الحالي" in html:
                    data = self._parse_acct_page(html, "")
                    return data, self._serialize_cookies(client)
            except Exception as e:
                logger.warning(f"fetch_with_session error: {e}")
        return None

    async def initiate_login(self, phone_number: str, password: str, device_uid: Optional[str] = None) -> Tuple[Dict[str, Any], bytes]:
        """
        Step 1 of interactive login:
        Fetches login page, extracts CSRF token and captcha image.
        Returns (session_state_dict, captcha_png_bytes).
        """
        uid = device_uid or str(uuid.uuid4())
        async with self._create_client() as client:
            try:
                # 1. GET /login
                res_login = await client.get(LOGIN_URL)
                html_login = decrypt_safeline_waf(res_login.text)
                soup = BeautifulSoup(html_login, 'html.parser')

                token_input = soup.find('input', {'name': '__RequestVerificationToken'})
                token = token_input['value'] if token_input else ""

                # 2. GET /captcha
                res_cap = await client.get(CAPTCHA_URL)
                captcha_bytes = res_cap.content

                session_state = {
                    "token": token,
                    "uid": uid,
                    "cookies": [
                        {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
                        for c in client.cookies.jar
                    ]
                }
                return session_state, captcha_bytes
            except Exception as e:
                raise ScraperError(f"تعذر الاتصال ببوابة يمن نت: {str(e)}")

    async def finalize_login(
        self,
        session_state: Dict[str, Any],
        phone_number: str,
        password: str,
        captcha_code: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        Step 2 of login:
        Submits credentials, captcha, and Remember=true.
        Returns (account_data_dict, updated_cookies_json).
        """
        cookies = session_state.get("cookies", [])
        token = session_state.get("token", "")
        uid = session_state.get("uid", str(uuid.uuid4()))

        async with self._create_client(cookies) as client:
            post_data = {
                "__RequestVerificationToken": token,
                "UId": uid,
                "Username": phone_number,
                "Password": password,
                "CapatchInput": captcha_code.strip(),
                "Remember": "true"
            }

            headers = {"Referer": LOGIN_URL, "Origin": BASE_URL}
            try:
                res = await client.post(LOGIN_URL, data=post_data, headers=headers)
                html = decrypt_safeline_waf(res.text)

                # Check if captcha failed
                if "رمز التحقق غير مطابق" in html:
                    raise ScraperError("❌ رمز التحقق (الكباتشا) غير مطابق! يرجى إعادة إدخال الرمز من الصورة الجديدة.")

                # Check if credentials failed
                if "كلمة المرور غير صحيحة" in html or "اسم المستخدم أو كلمة المرور" in html:
                    raise ScraperError("❌ بيانات الدخول غير صحيحة (تأكد من رقم الهاتف وكلمة المرور).")

                # If redirected or on acct
                if "بيانات الاشتراك" in html or "الرصيد الحالي" in html:
                    data = self._parse_acct_page(html, phone_number)
                    return data, self._serialize_cookies(client)

                # Try explicit GET /acct with the newly acquired cookies
                res_acct = await client.get(ACCT_URL)
                html_acct = decrypt_safeline_waf(res_acct.text)
                if "بيانات الاشتراك" in html_acct or "الرصيد الحالي" in html_acct:
                    data = self._parse_acct_page(html_acct, phone_number)
                    return data, self._serialize_cookies(client)

                raise ScraperError("⚠️ تعذر استخراج البيانات بعد تسجيل الدخول. قد يكون هيكل الصفحة قد تغير.")
            except ScraperError as se:
                raise se
            except Exception as e:
                raise ScraperError(f"حدث خطأ أثناء تسجيل الدخول: {str(e)}")

    async def fetch_account_data(
        self,
        phone_number: str,
        password: str,
        session_cookies: Optional[str] = None,
        device_uid: Optional[str] = None
    ) -> Tuple[Dict[str, Any], str]:
        """
        High-level method used by scheduler and sync handlers:
        1. If session_cookies & device_uid are available, tries fetching via session (no captcha).
        2. If expired or not present, raises CaptchaRequiredError containing new session_state and captcha bytes.
        """
        if session_cookies and device_uid:
            res = await self.fetch_with_session(session_cookies, device_uid)
            if res:
                return res

        # Needs login with captcha
        session_state, captcha_bytes = await self.initiate_login(phone_number, password, device_uid)
        raise CaptchaRequiredError(
            message="مطلوب إدخال رمز التحقق (كباتشا) لتسجيل الدخول وحفظ الجلسة.",
            session_state=session_state,
            captcha_bytes=captcha_bytes
        )
