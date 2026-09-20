import pytest
from services.scraper import YemenNetScraper

def test_scraper_parse_acct_page():
    sample_html = """
    <html>
        <head>
            <title>خدمة سوبرنت ADSL - علي محمد علي الخولاني</title>
        </head>
        <body>
            <table>
                <tr><td class="text-right h6">تاريخ التسجيل</td><td class="text-center">04/09/2013</td></tr>
                <tr><td class="text-right h6">باقة الاشتراك</td><td class="text-center">سوبرشامل-2-(54)جيجــا</td></tr>
                <tr><td class="text-right h6">حالة الاشتراك</td><td class="text-center">حساب نشط</td></tr>
                <tr><td class="text-right h6">رقم الهاتف</td><td class="text-center">1249590</td></tr>
                <tr><td class="text-right h6">الرصيد الحالي</td><td class="text-center">29٫88 جيجابايت</td></tr>
                <tr><td class="text-right h6">تاريخ انتهاء الصلاحية</td><td class="text-center">16/10/2026 08:01 م</td></tr>
            </table>
        </body>
    </html>
    """
    scraper = YemenNetScraper()
    result = scraper._parse_acct_page(sample_html, "1249590")

    assert result is not None
    assert result["subscriber_name"] == "علي محمد علي الخولاني"
    assert result["phone_number"] == "1249590"
    assert result["package_name"] == "سوبرشامل-2-(54)جيجــا"
    assert result["remaining_gb"] == 29.88
    assert result["total_gb"] == 54.0
    assert result["used_gb"] == 24.12
    assert "2026-10-16" in result["expiry_date"]
    assert result["days_left"] >= 0
