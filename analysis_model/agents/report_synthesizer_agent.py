# 3. 종합 리포트 생성 에이전트
## 앞서 생성한 자료들을 AnalysisState에 기반하여 최종 보고서를 생성한다



import json
from typing import Dict, Any, List

from ..state import AnalysisState, FinalReport, SelectedNews, MarketAnalysisResult

# --- 최종 보고서 생성 로직 ---

def build_prompt_context(state: AnalysisState) -> str:
    """
    LLM(HyperCLOVA X)에 전달할 프롬프트의 근거 데이터를 구성하는 함수.
    """
    print("[Report Synthesizer] 최종 보고서 생성을 위해 모든 근거 데이터를 종합합니다.")
    
    # state에서 필요한 모든 정보를 추출합니다.
    company_name = state.get("company_name")
    company_description = state.get("company_description")
    financial_health = state.get("financial_health")
    selected_news = state.get("selected_news", [])
    market_analysis = state.get("market_analysis_result")

    # 프롬프트에 들어갈 각 섹션을 구성합니다.
    context_parts = []
    
    # 1. 분석 대상 기업 정보
    context_parts.append("### 1. 분석 대상 기업 정보 ###")
    context_parts.append(f"- 기업명: {company_name}")
    context_parts.append(f"- 기업 개요: {company_description}")
    context_parts.append(f"- 재무 건전성 분석: {financial_health}\n")

    # 2. 핵심 뉴스 요약
    context_parts.append("### 2. 핵심 연관 뉴스 ###")
    if selected_news:
        for i, news in enumerate(selected_news, 1):
            context_parts.append(f"  - 뉴스 {i}: {news['title']}")
            context_parts.append(f"    요약: {news['summary']}")
            context_parts.append(f"    관련 지표: {', '.join(news['entities'])}\n")
    else:
        context_parts.append("  - 관련된 핵심 뉴스가 없습니다.\n")

    # 3. 시장 데이터 분석 결과
    context_parts.append("### 3. 시장 데이터 기반 상관관계 분석 ###")
    if market_analysis:
        context_parts.append(f"  - 분석 요약: {market_analysis['analysis_caption']}")
        context_parts.append(f"  - 근거 차트 경로: {market_analysis['chart_image_path']}\n")
    else:
        context_parts.append("  - 시장 데이터 분석 결과가 없습니다.\n")

    return "\n".join(context_parts)


def call_clova_api_for_report(context: str) -> str:
    """
    HyperCLOVA X API를 호출하여 최종 보고서를 생성하는 함수.
    """
    print("[Report Synthesizer] HyperCLOVA X API를 호출하여 보고서 초안을 요청합니다.")
    
    return 


# --- 에이전트 실행 함수 ---
def run_report_synthesizer(state: AnalysisState) -> Dict[str, Any]:
    """
    모든 근거 데이터를 종합하여 최종 보고서를 생성하는 에이전트.
    """
    print("\n--- 최종 보고서 생성 에이전트 실행 ---")
    
    # 1. LLM에 전달할 근거 데이터(컨텍스트) 생성
    prompt_context = build_prompt_context(state)
    
    # 2. Clova API를 호출하여 보고서 초안(JSON 문자열) 받기
    report_json_string = call_clova_api_for_report(prompt_context)
    
    # 3. JSON 문자열을 딕셔너리로 파싱
    try:
        final_report_data = json.loads(report_json_string)
    except json.JSONDecodeError:
        print("⚠️ [Report Synthesizer] Clova API 응답(JSON) 파싱에 실패했습니다.")
        return {}
        
    # 4. state.py에 정의된 FinalReport 형식에 맞춰 최종 결과 구성
    final_report: FinalReport = {
        "title": final_report_data.get("title", "제목 없음"),
        "executive_summary": final_report_data.get("executive_summary", ""),
        "key_findings": final_report_data.get("key_findings", []),
        "outlook": final_report_data.get("outlook", "")
    }
    
    print("✅ [Report Synthesizer] 최종 보고서 생성을 완료했습니다.")
    
    # 5. 완성된 보고서를 상태(State)에 추가하여 반환
    return {"final_report": final_report}
