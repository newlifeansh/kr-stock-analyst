from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.services.sga_analysis import parse_sga_document


def _sga_fixture() -> bytes:
    context = (
        "CFY2025dFY_ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis_"
        "ifrs-full_ConsolidatedMember_dart_ReportedAmountMember"
    )
    xml = f"""
    <document>
      <table><tr><te>당기</te><te>(단위 : 백만원)</te></tr></table>
      <table>
        <tr><te>판매비와관리비 합계</te><te acode="dart_TotalSellingGeneralAdministrativeExpenses" acontext="{context}" adecimal="-6" align="RIGHT">170</te></tr>
        <tr><te>급여</te><te acode="dart_SalariesWages" acontext="{context}" adecimal="-6" align="RIGHT">100</te></tr>
        <tr><te>복리후생비</te><te acode="dart_EmployeeBenefits" acontext="{context}" adecimal="-6" align="RIGHT">20</te></tr>
        <tr><te>연구개발비 총지출액</te><te acode="entity_ExpenditureOnResearchAndDevelopment" acontext="{context}" adecimal="-6" align="RIGHT">60</te></tr>
        <tr><te>개발비 자산화</te><te acode="entity_DevelopmentCostCapitalized" acontext="{context}" adecimal="-6" align="RIGHT">(10)</te></tr>
        <tr><te>경상개발비</te><te acode="dart_OrdinaryDevelopmentExpense" acontext="{context}" adecimal="-6" align="RIGHT">50</te></tr>
      </table>
    </document>
    """
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("report.xml", xml)
    return output.getvalue()


def _income_statement_false_positive_fixture() -> bytes:
    current = (
        "CFY2025dFY_ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis_"
        "ifrs-full_ConsolidatedMember_dart_ReportedAmountMember"
    )
    previous = current.replace("CFY2025", "PFY2024")
    rows = []
    for context, revenue, sga in ((current, "10891443", "-573870"), (previous, "9077200", "-450617")):
        rows.extend(
            [
                f'<tr><te>매출액</te><te acontext="{context}" adecimal="-6" align="RIGHT">{revenue}</te></tr>',
                f'<tr><te>매출원가</te><te acontext="{context}" adecimal="-6" align="RIGHT">-8856371</te></tr>',
                f'<tr><te>판매비와관리비</te><te acontext="{context}" adecimal="-6" align="RIGHT">{sga}</te></tr>',
                f'<tr><te>당기순이익</te><te acontext="{context}" adecimal="-6" align="RIGHT">1878732</te></tr>',
                f'<tr><te>순확정급여부채의 재측정요소</te><te acontext="{context}" adecimal="-6" align="RIGHT">2720</te></tr>',
            ]
        )
    xml = f"""
    <document>
      <table><tr><te>당기</te><te>(단위 : 백만원)</te></tr></table>
      <table>{''.join(rows)}</table>
    </document>
    """
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("report.xml", xml)
    return output.getvalue()


def test_sga_parser_prefers_consolidated_current_period_and_removes_rnd_duplicates():
    payload = parse_sga_document(_sga_fixture(), fallback_year=2025)

    assert payload is not None
    assert payload["period"] == "2025"
    assert payload["consolidated"] is True
    assert payload["total_amount"] == Decimal("1.70")
    assert payload["coverage_ratio"] == Decimal("100.0")
    categories = {item["key"]: item for item in payload["categories"]}
    assert categories["labor"]["amount"] == Decimal("1.00")
    assert categories["benefits"]["amount"] == Decimal("0.20")
    assert categories["research"]["amount"] == Decimal("0.50")
    assert [item["name"] for item in categories["research"]["details"]] == ["경상개발비"]


def test_sga_parser_rejects_primary_statement_with_repeated_benefit_line():
    assert parse_sga_document(_income_statement_false_positive_fixture(), fallback_year=2025) is None


def test_sga_endpoint_exposes_read_only_company_analysis(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "build_sga_analysis",
        lambda *_args, **_kwargs: {
            "code": "000660",
            "name": "SK하이닉스",
            "available": True,
            "detail_available": True,
            "period": "2025",
            "consolidated": True,
            "unit": "억원",
            "revenue": "971467",
            "total_amount": "114844.71",
            "sales_ratio": "11.82",
            "coverage_ratio": "100.0",
            "categories": [
                {
                    "key": "labor",
                    "label": "인건비",
                    "amount": "19065.74",
                    "sales_ratio": "1.96",
                    "share_of_sga": "16.60",
                    "details": [{"name": "급여", "amount": "18593.24", "sales_ratio": "1.91"}],
                }
            ],
            "source": "DART 사업보고서 주석",
            "source_url": "https://dart.fss.or.kr/example",
            "message": "연결재무제표 주석 기준",
        },
    )
    response = TestClient(app).get("/stocks/000660/sga-analysis?refresh=true")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["categories"][0]["label"] == "인건비"
