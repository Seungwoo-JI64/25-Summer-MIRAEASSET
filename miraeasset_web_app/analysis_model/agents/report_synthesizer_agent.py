# analysis_model/agents/report_synthesizer_agent.py

import os
import json
import requests
from typing import Dict, Any, Set

from ..state import AnalysisState, FinalReport
from .news_analyst_agent import METRICS_MAP

def call_clova_api(prompt: str) -> str | None:
    """Clova Studio API를 호출하고 최종 응답 문자열을 반환하는 범용 함수"""
    host = 'https://clovastudio.stream.ntruss.com'
    api_key = os.environ.get("CLOVA_API_KEY")
    request_id = os.environ.get("CLOVA_REQUEST_ID")
    if not all([api_key, request_id]):
        raise EnvironmentError("환경 변수에 CLOVA_API_KEY, CLOVA_REQUEST_ID를 설정해야 합니다.")
    headers = {
        'Authorization': f'Bearer {api_key}', 'X-NCP-CLOVASTUDIO-REQUEST-ID': request_id,
        'Content-Type': 'application/json; charset=utf-8', 'Accept': 'text/event-stream'
    }
    request_data = {
        'messages': [{"role": "user", "content": prompt}], 'topP': 0.8, 'topK': 0, 'maxTokens': 4096,
        'temperature': 0.5, 'repetitionPenalty': 1.1, 'stopBefore': [], 'includeAiFilters': True,
    }
    try:
        with requests.post(host + '/testapp/v3/chat-completions/HCX-DASH-002',
                           headers=headers, json=request_data, stream=True) as r:
            r.raise_for_status()
            final_content = None
            for line in r.iter_lines():
                if not line or b'data: [DONE]' in line: continue
                if line.startswith(b'data:'):
                    try:
                        json_str = line.decode('utf-8')[len('data:'):].strip()
                        data = json.loads(json_str)
                        if 'message' in data and 'content' in data['message'] and data['message']['content']:
                            final_content = data['message']['content']
                    except (json.JSONDecodeError, KeyError): continue
            return final_content
    except Exception as e:
        print(f"⚠️ API 호출/처리 중 오류 발생: {e}")
        return None

def _cleanup_string_values(data: Any) -> Any:
    """
    JSON 객체(dict, list) 내의 모든 문자열 값에서 줄바꿈을 제거하고 공백을 정리합니다.
    """
    if isinstance(data, dict):
        return {k: _cleanup_string_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_cleanup_string_values(item) for item in data]
    if isinstance(data, str):
        return ' '.join(data.replace('\n', ' ').split())
    return data

def _generate_entity_analysis(state: AnalysisState) -> Dict | None:
    """1단계: '분석가 LLM' - 개별 주체 심층 분석 JSON 생성"""
    print("  - [1단계] '분석가 LLM' 호출: 개별 주체 심층 분석 요청")
    target_ticker = state.get("ticker")
    target_name = state.get("company_name", "N/A")
    selected_news = state.get("selected_news", [])
    selected_domestic_news = state.get("selected_domestic_news", []) # <<< 국내 뉴스 가져오기
    news_impact_data = state.get("market_analysis_result", {}).get("news_impact_data", [])

    # ▼▼▼▼▼▼▼▼▼▼ 수정된 부분 ▼▼▼▼▼▼▼▼▼▼
    # 해외 뉴스 + 국내 뉴스에서 모든 관련 지표를 취합합니다.
    all_related_metrics: Set[str] = set()
    for news in selected_news:
        all_related_metrics.update(news.get("related_metrics", []))
    for news in selected_domestic_news:
        all_related_metrics.update(news.get("related_metrics", []))
    # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
    
    ticker_to_name_map = {target_ticker: target_name, **{t: i['name'] for t, i in METRICS_MAP.items()}}
    entities_to_analyze = [f"{ticker_to_name_map.get(t, t)}({t})" for t in all_related_metrics]
    entities_list_str = ", ".join(entities_to_analyze)

    prompt = f"""
## GOAL
Analyze the provided financial data to generate the `entity_analysis` part of an investment briefing.

## CRITICAL INSTRUCTIONS
1. Your entire response MUST be a single, valid JSON object that contains ONLY the `entity_analysis` key.
2. The `entity_analysis` object MUST contain a key for EACH of the following entities: **{entities_list_str}**. Do not omit any entity.
3. For each entity, your analysis ('내용') must specifically describe its impact on `{target_name}`, referencing the detailed daily price data (`상세 주가`) to find specific dates of influence (time-lag analysis).
4. **All string values inside the JSON must be a single line of text without any newline characters (`\\n`). The text must flow naturally.**

## JSON OUTPUT FORMAT
```json
{{
  "entity_analysis": {{
    "분석대상_이름(티커)": {{
      "내용": "이 주체(기업/지수)의 상황이 분석 대상 기업에 미치는 구체적인 영향과 전망을 분석한 내용을 서술. 특히, 제공된 일별 상세 주가 데이터를 참고하여 '어떤 날짜'의 움직임이 '어떤 영향'을 주었는지 명시할 것.",
      "주가_반응": "분석 기간 동안 이 주체의 주가 변동 요약"
    }}
  }}
}}
```

## DATA FOR ANALYSIS
{json.dumps(news_impact_data, indent=2, ensure_ascii=False)}

## TASK
Now, generate the JSON object based on all the instructions and data provided above.
"""
    response_str = call_clova_api(prompt)
    if not response_str: return None

    try:
        clean_str = response_str.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_str)
        cleaned_data = _cleanup_string_values(data)
        return cleaned_data.get("entity_analysis", {})
    except json.JSONDecodeError:
        print("  - ⚠️ [1단계] 분석가 LLM의 응답이 유효한 JSON 형식이 아닙니다.")
        return None

def _generate_final_report(state: AnalysisState, entity_analysis: Dict) -> Dict | None:
    """2단계: '작성가 LLM' - 최종 보고서의 나머지 부분 작성"""
    print("  - [2단계] '작성가 LLM' 호출: 최종 보고서 작성 요청")
    target_name = state.get("company_name", "N/A")
    correlation_summary = state.get("market_analysis_result", {}).get("correlation_summary", [])
    
    prompt = f"""
## GOAL
You are a top-tier securities analyst. Write a professional investment briefing for `{target_name}`.

## INSTRUCTIONS
1. Use the pre-analyzed `entity_analysis` and other data to write the final report.
2. Your entire response MUST be a single, valid JSON object that follows the `JSON OUTPUT FORMAT`.
3. **All string values inside the JSON must be a single line of text without any newline characters (`\\n`).**

## JSON OUTPUT FORMAT
```json
{{
  "report_title": "[오늘의 투자 브리핑] OOO 기업 관련 주요 동향 및 전략",
  "briefing_summary": "어제까지의 미국 증시 및 관련주 마감 현황을 요약하고, 분석 대상 기업의 최근 주가 동향과 가장 중요한 장기 상관관계를 언급하며 오늘 시장의 핵심 포인트를 2-3 문장으로 제시.",
  "strategy_suggestion": "모든 분석을 종합하여 오늘의 투자 전략을 구체적인 시나리오를 포함하여 한 문단으로 작성."
}}
```

## DATA FOR ANALYSIS
**1. Target Company**: {target_name}
**2. Long-term Correlation Analysis**: 
{json.dumps(correlation_summary, indent=2, ensure_ascii=False)}
**3. In-depth Entity Analysis (Pre-analyzed by Analyst LLM)**: 
{json.dumps(entity_analysis, indent=2, ensure_ascii=False)}

## TASK
Now, generate the final briefing JSON object based on all the data provided above.
"""
    response_str = call_clova_api(prompt)
    if not response_str: return None

    try:
        clean_str = response_str.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_str)
        return _cleanup_string_values(data)
    except json.JSONDecodeError:
        print("  - ⚠️ [2단계] 작성가 LLM의 응답이 유효한 JSON 형식이 아닙니다.")
        return None

def run_report_synthesizer(state: AnalysisState) -> Dict[str, Any]:
    """Multi-LLM 구조를 사용하여 최종 투자 브리핑을 생성하는 메인 함수"""
    print("\n--- ✍️ 최종 투자 브리핑 생성 에이전트 (Multi-LLM) 실행 ---")

    entity_analysis = _generate_entity_analysis(state)
    if not entity_analysis:
        print("⚠️ [Report Synthesizer] 1단계 분석 실패. 프로세스를 중단합니다.")
        return {}

    final_report_parts = _generate_final_report(state, entity_analysis)
    if not final_report_parts:
        print("⚠️ [Report Synthesizer] 2단계 작성 실패. 프로세스를 중단합니다.")
        return {}

    final_report_structured = FinalReport(
        report_title=final_report_parts.get("report_title", "제목 없음"),
        briefing_summary=final_report_parts.get("briefing_summary", "내용 없음"),
        news_analysis={"entity_analysis": entity_analysis},
        strategy_suggestion=final_report_parts.get("strategy_suggestion", "내용 없음")
    )
    
    print("✅ [Report Synthesizer] Multi-LLM 기반 최종 브리핑 생성을 완료했습니다.")
    return {"final_report": final_report_structured}
