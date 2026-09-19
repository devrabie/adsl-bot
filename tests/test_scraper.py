import pytest
from bs4 import BeautifulSoup
from services.scraper import YemenNetScraper

def test_scraper_parse_portal_html():
    sample_html = """
    <html>
        <body>
            <div id="lblCredit">الرصيد المتبقي : 45.5 GB</div>
            <div id="lblTotal">الرصيد الكلي : 100 GB</div>
            <div id="lblExpire">تاريخ الانتهاء: 2025-12-31</div>
            <div id="lblDays">الأيام المتبقية : 15 يوم</div>
        </body>
    </html>
    """
    scraper = YemenNetScraper()
    soup = BeautifulSoup(sample_html, "html.parser")
    result = scraper._parse_portal_html(soup, "01234567")

    assert result is not None
    assert result["phone_number"] == "01234567"
    assert result["remaining_gb"] == 45.5
    assert result["total_gb"] == 100.0
    assert result["used_gb"] == 54.5
    assert result["expiry_date"] == "2025-12-31"
    assert result["days_left"] == 15
