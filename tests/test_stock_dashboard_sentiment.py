from app.services.stock_dashboard import _keyword_impact, _keyword_score


def test_news_keyword_impact_labels_market_direction():
    assert _keyword_impact(_keyword_score("삼성전자 수혜 기대에 상승")) == "호재"
    assert _keyword_impact(_keyword_score("실적 우려에 외국인 매도와 급락")) == "악재"
    assert _keyword_impact(_keyword_score("정기 주주총회 개최")) == "중립"
