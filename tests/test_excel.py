import os
import pytest
import openpyxl
from services.excel_generator import generate_dsl_report_excel

def test_generate_dsl_report_excel(tmp_path):
    output_file = tmp_path / "test_report.xlsx"
    lines_data = [
        {
            "id": 1,
            "phone_number": "01234567",
            "total_gb": 100.0,
            "used_gb": 92.0,
            "remaining_gb": 8.0,
            "net_consumption_24h": 3.5,
            "expiry_date": "2025-12-31",
            "days_left": 3,
            "status_str": "حرج",
            "last_error": None
        },
        {
            "id": 2,
            "phone_number": "01765432",
            "total_gb": 200.0,
            "used_gb": 160.0,
            "remaining_gb": 40.0,
            "net_consumption_24h": 5.0,
            "expiry_date": "2025-12-30",
            "days_left": 9,
            "status_str": "تنبيه",
            "last_error": None
        }
    ]

    res_path = generate_dsl_report_excel(lines_data, str(output_file))
    assert os.path.exists(res_path)

    wb = openpyxl.load_workbook(res_path)
    sheet = wb.active
    assert sheet.views.sheetView[0].rightToLeft is True
    assert sheet.cell(row=4, column=2).value == "01234567"
    assert sheet.cell(row=4, column=5).value == 8.0
