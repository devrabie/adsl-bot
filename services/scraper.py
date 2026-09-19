import re
import logging
from typing import Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://adsl.yemen.net.ye"
LOGIN_URL = f"{BASE_URL}/adsl/login.aspx"
DASHBOARD_URL = f"{BASE_URL}/adsl/user_info.aspx"

class ScraperError(Exception):
    """Custom exception for scraper failures."""
    pass

class YemenNetScraper:
    def __init__(self, timeout: int = 15, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    async def fetch_account_data(self, phone_number: str, password: str) -> Dict[str, Any]:
        """
        Logs into Yemen Net ADSL portal and extracts usage and validity data.
        Returns a dict:
        {
            "phone_number": str,
            "total_gb": float,
            "used_gb": float,
            "remaining_gb": float,
            "expiry_date": str,
            "days_left": int,
            "status": "success"
        }
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ar,en;q=0.9",
        }

        async with httpx.AsyncClient(headers=headers, timeout=self.timeout, follow_redirects=True, verify=False) as client:
            last_exception = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    # Step 1: GET Login Page to fetch ASP.NET viewstates
                    login_page_res = await client.get(LOGIN_URL)
                    soup_login = BeautifulSoup(login_page_res.text, "html.parser")
                    viewstate = self._extract_input_value(soup_login, "__VIEWSTATE")
                    eventvalidation = self._extract_input_value(soup_login, "__EVENTVALIDATION")
                    viewstategenerator = self._extract_input_value(soup_login, "__VIEWSTATEGENERATOR")

                    # ASP.NET form fields for Yemen Net portal
                    form_data = {
                        "__VIEWSTATE": viewstate,
                        "__EVENTVALIDATION": eventvalidation,
                        "__VIEWSTATEGENERATOR": viewstategenerator,
                        "txtUsername": phone_number,
                        "txtPassword": password,
                        "btnLogin": "تسجيل الدخول",
                    }

                    # Step 2: POST credentials
                    post_res = await client.post(LOGIN_URL, data=form_data)

                    # Check if login failed or landed on dashboard/info page
                    if "كلمة المرور غير صحيحة" in post_res.text or "اسم المستخدم غير صحيح" in post_res.text or ("Error" in post_res.text and "login" in str(post_res.url).lower()):
                        raise ScraperError("بيانات الدخول غير صحيحة (رقم الخط أو كلمة السر خطأ)")

                    # Step 3: Parse response HTML for data
                    soup_dash = BeautifulSoup(post_res.text, "html.parser")
                    parsed_data = self._parse_portal_html(soup_dash, phone_number)

                    if parsed_data:
                        return parsed_data

                    # If parsing failed on post response, try explicit GET dashboard
                    dash_res = await client.get(DASHBOARD_URL)
                    soup_dash2 = BeautifulSoup(dash_res.text, "html.parser")
                    parsed_data2 = self._parse_portal_html(soup_dash2, phone_number)
                    if parsed_data2:
                        return parsed_data2

                    raise ScraperError("تعذر استخراج البيانات من بوابة المشتركين (تغير في هيكل الصفحة)")

                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    last_exception = ScraperError(f"خطأ في الاتصال بموقع يمن نت: {str(e)}")
                    logger.warning(f"Attempt {attempt} failed for {phone_number}: {e}")
                except ScraperError as e:
                    raise e
                except Exception as e:
                    last_exception = ScraperError(f"خطأ غير متوقع أثناء الفحص: {str(e)}")
                    logger.warning(f"Attempt {attempt} unexpected error for {phone_number}: {e}")

            if last_exception:
                raise last_exception
            raise ScraperError("فشل الاتصال بالموقع بعد عدة محاولات")

    def _extract_input_value(self, soup: BeautifulSoup, element_id: str) -> str:
        elem = soup.find("input", {"id": element_id})
        if elem and elem.has_attr("value"):
            return elem["value"]
        return ""

    def _parse_portal_html(self, soup: BeautifulSoup, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Parses Yemen Net ADSL page HTML tables and spans.
        Extracts: Total GB, Used GB, Remaining GB, Expiry Date, Remaining Days.
        """
        page_text = soup.get_text()

        # Check if logged in successfully by keywords in text
        if "رصيد" not in page_text and "المتبقي" not in page_text and "الرصيد" not in page_text:
            return None

        total_gb = 0.0
        used_gb = 0.0
        remaining_gb = 0.0
        expiry_date = ""
        days_left = 0

        # Helper function to find numbers near key phrases
        # Look for remaining GB
        rem_match = re.search(r'(?:الرصيد المتبقي|المتبقي)\s*[:\t\n\r]*\s*([\d\.]+)\s*(?:جيجا|جيجابايت|GB|MB)?', page_text, re.IGNORECASE)
        if rem_match:
            try:
                remaining_gb = float(rem_match.group(1))
            except ValueError:
                pass

        # Total GB
        tot_match = re.search(r'(?:الرصيد الكلي|إجمالي الرصيد|الرصيد الإجمالي)\s*[:\t\n\r]*\s*([\d\.]+)\s*(?:جيجا|جيجابايت|GB|MB)?', page_text, re.IGNORECASE)
        if tot_match:
            try:
                total_gb = float(tot_match.group(1))
            except ValueError:
                pass

        # Used GB
        used_match = re.search(r'(?:المستهلك|الرصيد المستهلك)\s*[:\t\n\r]*\s*([\d\.]+)\s*(?:جيجا|جيجابايت|GB|MB)?', page_text, re.IGNORECASE)
        if used_match:
            try:
                used_gb = float(used_match.group(1))
            except ValueError:
                pass

        # Expiry Date
        exp_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})', page_text)
        if exp_match:
            expiry_date = exp_match.group(1)

        # Days left
        days_match = re.search(r'(?:الأيام المتبقية|عدد الأيام المتبقية|المتبقي من الأيام)\s*[:\t\n\r]*\s*(\d+)', page_text)
        if days_match:
            try:
                days_left = int(days_match.group(1))
            except ValueError:
                pass

        # Also search in specific HTML elements by ID/Class common in YemenNet portals
        lbl_rem = soup.find(id=re.compile(r'lblRemaining|lblBalance|lblCredit', re.I))
        if lbl_rem and lbl_rem.text:
            num = re.search(r'[\d\.]+', lbl_rem.text)
            if num:
                remaining_gb = float(num.group(0))

        lbl_tot = soup.find(id=re.compile(r'lblTotal|lblCapacity', re.I))
        if lbl_tot and lbl_tot.text:
            num = re.search(r'[\d\.]+', lbl_tot.text)
            if num:
                total_gb = float(num.group(0))

        lbl_exp = soup.find(id=re.compile(r'lblExpire|lblExpiryDate', re.I))
        if lbl_exp and lbl_exp.text:
            exp_date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})', lbl_exp.text)
            if exp_date_match:
                expiry_date = exp_date_match.group(1)

        lbl_days = soup.find(id=re.compile(r'lblDays|lblRemainingDays', re.I))
        if lbl_days and lbl_days.text:
            num = re.search(r'\d+', lbl_days.text)
            if num:
                days_left = int(num.group(0))

        if used_gb == 0.0 and total_gb > 0.0 and remaining_gb > 0.0:
            used_gb = round(max(0.0, total_gb - remaining_gb), 2)
        elif total_gb == 0.0 and used_gb > 0.0 and remaining_gb > 0.0:
            total_gb = round(used_gb + remaining_gb, 2)

        return {
            "phone_number": phone_number,
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "remaining_gb": round(remaining_gb, 2),
            "expiry_date": expiry_date or "غير محدد",
            "days_left": days_left,
            "status": "success"
        }
