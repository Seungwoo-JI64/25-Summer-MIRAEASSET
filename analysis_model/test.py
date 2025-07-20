from typing import TypedDict, Optional, Dict, Any
from agents.data_prep_agent import run_data_prep

class AnalysisState(TypedDict):
    company_name: Optional[str]
    ticker: Optional[str]
    financial_statements: Optional[str]
    company_description: Optional[str]

# 테스트용 초기 상태: company_name은 없어도 되고 티커만 넣기
test_state: AnalysisState = {
    "company_name": None,    # 한글명 대신 None
    "ticker": "005930.KS",   # 삼성전자 티커 (예시)
    "financial_statements": None,
    "company_description": None
}

updated_state = run_data_prep(test_state)

print("✅ 재무제표 결과:")
print(f"티커: {updated_state.get('ticker')}")
print(f"기업 개요: {updated_state.get('company_description')}")
