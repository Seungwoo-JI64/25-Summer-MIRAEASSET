# analysis_model/test.py

import os
from dotenv import load_dotenv
from pprint import pprint

# .env 파일의 환경 변수를 다른 모듈 import 전에 가장 먼저 로드합니다.
load_dotenv()

# 패키지 내 상대 경로 import
from .state import AnalysisState
from .agents.data_prep_agent import run_data_prep
from .agents.news_analyst_agent import run_news_analyst
from .agents.domestic_news_analyst_agent import run_domestic_news_analyst
from .agents.market_correlation_agent import run_market_correlation
from .agents.report_synthesizer_agent import run_report_synthesizer

# --- 테스트 실행 ---

# 1. 분석을 시작할 기업 티커로 초기 상태를 설정합니다.
initial_state: AnalysisState = {
    "ticker": "000660.KS",  # SK하이닉스 예시
    "company_name": None,
    "company_description": None,
    "financial_health": None,
    "selected_news": None,
    "selected_domestic_news": None,
    "market_analysis_result": None,
    "final_report": None,
}

print(f"🚀 '{initial_state['ticker']}' 기업에 대한 전체 분석 파이프라인 테스트를 시작합니다.")
print("=" * 60)

# --- 파이프라인 순차 실행 ---
current_state = initial_state.copy()

print("\n--- [1/5] 데이터 준비 에이전트 ---")
current_state.update(run_data_prep(current_state))
print("✅ 완료")

print("\n--- [2/5] 해외 뉴스 분석 에이전트 ---")
current_state.update(run_news_analyst(current_state))
print("✅ 완료")

print("\n--- [3/5] 국내 뉴스 분석 에이전트 ---")
current_state.update(run_domestic_news_analyst(current_state))
print("✅ 완료")

print("\n--- [4/5] 시장 데이터 분석 에이전트 ---")
current_state.update(run_market_correlation(current_state))
print("✅ 완료")

print("\n--- [5/5] 최종 투자 브리핑 생성 에이전트 ---")
current_state.update(run_report_synthesizer(current_state))
print("✅ 완료")

# --- 최종 결과 확인 ---
print("\n\n" + "=" * 20 + " 최종 생성된 투자 브리핑 (JSON) " + "=" * 20)

final_report = current_state.get("final_report")
if final_report:
    # pprint를 사용하여 최종 결과를 있는 그대로 출력합니다.
    pprint(final_report)
else:
    print("최종 보고서가 생성되지 않았습니다.")

print("\n" + "=" * 60)
