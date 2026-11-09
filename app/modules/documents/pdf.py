import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TITLES = {
    "EMPLOYMENT": "재직증명서",
    "CAREER": "경력증명서",
    "PAYSLIP": "급여명세서",
    "WITHHOLDING": "원천징수 내역(간이)",
}
LABELS = {
    "employee_no": "사번",
    "name": "성명",
    "birth_date": "생년월일",
    "department_name": "부서",
    "position_name": "직급",
    "job_name": "직무",
    "hire_date": "입사일",
    "termination_date": "퇴사일",
    "as_of": "기준일",
    "pay_month": "급여월",
    "paid_at": "지급일",
    "status": "상태",
    "base_salary": "기본급",
    "position_allowance": "직책수당",
    "meal_allowance": "식대",
    "other_allowance": "기타수당",
    "gross_pay": "총 지급액",
    "national_pension": "국민연금",
    "health_insurance": "건강보험",
    "long_term_care": "장기요양보험",
    "employment_insurance": "고용보험",
    "income_tax": "소득세",
    "local_income_tax": "지방소득세",
    "total_deduction": "총 공제액",
    "net_pay": "실수령액",
    "year": "귀속 연도",
    "months": "지급 개월",
    "first_month": "최초 지급월",
    "last_month": "최종 지급월",
    "social_insurance": "사회보험 합계",
}


def font_name():
    if "HRISKorean" in pdfmetrics.getRegisteredFontNames():
        return "HRISKorean"
    paths = [
        os.getenv("PDF_FONT_PATH", ""),
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]
    for value in paths:
        if value and Path(value).is_file():
            pdfmetrics.registerFont(TTFont("HRISKorean", value))
            return "HRISKorean"
    if "HYSMyeongJo-Medium" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    return "HYSMyeongJo-Medium"


def render_pdf(path, document_type, company, employee, payload, issued_at):
    font = font_name()
    normal = ParagraphStyle("normal", fontName=font, fontSize=10, leading=16, wordWrap="CJK")
    title = ParagraphStyle("title", parent=normal, fontSize=20, leading=30, spaceAfter=20)
    story = [
        Paragraph(TITLES[document_type], title),
        Paragraph(escape(company["company_name"]), normal),
        Paragraph(escape(f"{employee['employee_no']} · {employee['employee_name']}"), normal),
        Spacer(1, 16),
    ]
    rows = []
    for key, value in payload.items():
        if key == "career":
            continue
        rendered = "-" if value is None else str(value)
        rows.append(
            [Paragraph(escape(LABELS.get(key, key)), normal), Paragraph(escape(rendered), normal)]
        )
    table = Table(rows, colWidths=[140, 340], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f6")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#ccd3dc")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([table, Spacer(1, 16)])
    if payload.get("career"):
        for row in payload["career"]:
            text = f"{row['effective_date']} · {row['action_type']} · {row['department_name']} · {row['position_name']}"
            story.append(Paragraph(escape(text), normal))
        story.append(Spacer(1, 16))
    if document_type == "WITHHOLDING":
        story.append(
            Paragraph(
                "저장된 지급 완료 내역을 합산한 간이 자료이며 연말정산은 반영하지 않습니다.", normal
            )
        )
    story.append(
        Paragraph(escape(f"발급일시: {issued_at.isoformat(timespec='seconds')} +09:00"), normal)
    )
    SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=48,
        bottomMargin=48,
        title=TITLES[document_type],
    ).build(story)
