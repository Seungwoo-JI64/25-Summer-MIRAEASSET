# 4. 최종 보고서 생성 에이전트

import os
import json
import requests
from typing import Dict, Any, Set

from ..state import AnalysisState, FinalReport
from .news_analyst_agent import METRICS_MAP

########################################################
def call_clova_api(prompt: str) -> str | None:
    """Clova X API를 호출하고 최종 보고서 생성 함수"""
    # Clova X 환경변수
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
        'messages': [{"role": "user", "content": prompt}], 'topP': 0.8, 'topK': 0, 'maxTokens': 4096, # 장문의 보고서를 작성해야하기 때문에 토큰수를 최대로 증가
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
        print(f"API 호출/처리 중 오류 발생: {e}")
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

def _get_entities_to_analyze(state: AnalysisState) -> list[str]:
    """분석해야 할 모든 고유 엔티티(티커) 목록을 state에서 추출하는 헬퍼 함수"""
    target_ticker = state.get("ticker")
    target_name = state.get("company_name", "N/A")
    selected_news = state.get("selected_news", [])
    selected_domestic_news = state.get("selected_domestic_news", [])
    
    all_related_metrics: Set[str] = set()
    for news in selected_news:
        all_related_metrics.update(news.get("related_metrics", []))
    for news in selected_domestic_news:
        all_related_metrics.update(news.get("related_metrics", []))
        
    ticker_to_name_map = {target_ticker: target_name, **{t: i['name'] for t, i in METRICS_MAP.items()}}
    return [f"{ticker_to_name_map.get(t, t)}({t})" for t in all_related_metrics]


def _generate_single_entity_analysis(state: AnalysisState, entity_key: str) -> Dict | None:
    """'분석가 LLM' - 단일 주체에 대한 심층 분석 JSON 생성"""
    target_name = state.get("company_name", "N/A")
    news_impact_data = state.get("market_analysis_result", {}).get("news_impact_data", [])

    prompt = f"""
## GOAL
Analyze how the single entity `{entity_key}` impacts the target company `{target_name}`, based on the provided financial data.

## CRITICAL INSTRUCTIONS
1. Your entire response MUST be a single, valid JSON object.
2. The JSON should contain your analysis under two keys: "내용" and "주가_반응".
3. Your analysis ('내용') must specifically describe the impact on `{target_name}`, referencing the detailed daily price data (`상세 주가`) to find specific dates of influence.
4. All string values inside the JSON must be a single line of text without newline characters (`\\n`).

## JSON OUTPUT FORMAT
```json
{{
  "내용": "이 주체({entity_key})의 상황이 분석 대상 기업({target_name})에 미치는 구체적인 영향과 전망을 분석한 내용을 서술.",
  "주가_반응": "분석 기간 동안 이 주체({entity_key})의 주가 변동 요약"
}}
```

## DATA FOR ANALYSIS
{json.dumps(news_impact_data, indent=2, ensure_ascii=False)}

## TASK
Now, generate the JSON object for `{entity_key}` based on all the instructions and data.
"""
    response_str = call_clova_api(prompt)
    if not response_str: return None

    try:
        clean_str = response_str.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_str)
        return _cleanup_string_values(data)
    except json.JSONDecodeError:
        print(f"[분석가 LLM] '{entity_key}' 분석 결과가 유효한 JSON이 아닙니다.")
        return None

def _generate_briefing_summary(state: AnalysisState, entity_analysis: Dict, financial_health: str, news_summaries: str) -> str | None:
    """'요약가 LLM' - 전체 분석 내용을 요약하는 문단 생성"""
    target_name = state.get("company_name", "N/A")
    
    prompt = f"""
## GOAL
You are a financial analyst summarizing a detailed report for a client. Your task is to create a concise summary of the pre-analyzed data about `{target_name}`.

## INSTRUCTIONS
1. Your entire response MUST be a single, valid JSON object with one key: "briefing_summary".
2. The summary should be 2-3 sentences, highlighting the most critical positive and negative factors found in the analysis.
3. **Do not just list the analyzed entities. Synthesize the core findings into a coherent summary.**
4. The string value must be a single line of text without newline characters (`\\n`).

## JSON OUTPUT FORMAT
```json
{{
  "briefing_summary": "분석된 내용을 바탕으로, {target_name}에 대한 핵심적인 긍정, 부정 요인을 종합한 2-3 문장의 요약문을 작성."
}}
```

## DATA TO SUMMARIZE
** 1. Target Company's Financial Health (Pre-analyzed):**
{financial_health}
** 2. In-depth Entity Analysis (Pre-analyzed)**: 
{json.dumps(entity_analysis, indent=2, ensure_ascii=False)}
** 3. Key News Summaries**: 
{news_summaries}

## TASK
Now, generate the summary JSON object based on the provided analysis.
"""
    response_str = call_clova_api(prompt)
    if not response_str: return None

    try:
        clean_str = response_str.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_str)
        return _cleanup_string_values(data).get("briefing_summary")
    except json.JSONDecodeError:
        print("[요약가 LLM] 응답이 유효한 JSON 형식이 아닙니다.")
        return None

def _generate_strategy_suggestion(state: AnalysisState, entity_analysis: Dict, financial_health: str, news_summaries: str) -> str | None:
    """'전략가 LLM' - 최종 투자 전략 제안 문단 생성 (개인 투자자 관점으로 수정)"""
    target_name = state.get("company_name", "N/A")
    correlation_summary = state.get("market_analysis_result", {}).get("correlation_summary", [])
    
    prompt = f"""
## GOAL
You are a top-tier securities analyst writing for a **personal investor** who is considering investing in `{target_name}`. Your task is to provide a concrete, actionable investment strategy from their perspective.

## INSTRUCTIONS
1. Your entire response MUST be a single, valid JSON object with one key: "strategy_suggestion".
2. **The strategy must be from the viewpoint of an individual investor, NOT corporate management.** Advise on what the investor should do or watch for.
3. Provide specific buy/sell/hold signals based on the analyzed data. For example, "An investor should consider buying if X happens, but should be cautious if Y trend continues."
4. The string value must be a single line of text without newline characters (`\\n`).

## JSON OUTPUT FORMAT
```json
{{
  "strategy_suggestion": "개인 투자자의 관점에서, 모든 분석 내용을 종합하여 '무엇을, 어떻게' 해야 하는지에 대한 구체적인 투자 전략을 한 문단으로 작성."
}}
```

## DATA FOR ANALYSIS
**1. Target Company**: {target_name}
**2. Target Company's Financial Health**: 
{financial_health}
**3. Long-term Correlation Analysis**: 
{json.dumps(correlation_summary, indent=2, ensure_ascii=False)}
**4. In-depth Entity Analysis (Pre-analyzed)**: 
{json.dumps(entity_analysis, indent=2, ensure_ascii=False)}
**5. Key News Summaries**:
{news_summaries}

## TASK
Now, generate the investment strategy JSON object for a personal investor.
"""
    response_str = call_clova_api(prompt)
    if not response_str: return None

    try:
        clean_str = response_str.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_str)
        return _cleanup_string_values(data).get("strategy_suggestion")
    except json.JSONDecodeError:
        print("[전략가 LLM] 응답이 유효한 JSON 형식이 아닙니다.")
        return None


def run_report_synthesizer(state: AnalysisState) -> Dict[str, Any]:
    """개별 LLM 호출 구조를 사용하여 최종 투자 브리핑을 생성하는 메인 함수"""
    print("\n--- 최종 투자 브리핑 생성 에이전트 (개별 호출 구조) 실행 ---")
    
    target_name = state.get("company_name", "N/A")
    # State에서 financial_health 값을 가져옵니다.
    financial_health = state.get("financial_health", "재무 건전성 보고서 정보가 없습니다.")

    selected_news = state.get("selected_news", []) or []
    selected_domestic_news = state.get("selected_domestic_news", []) or []
    all_news = selected_news + selected_domestic_news
    
    news_summaries_text = "\n".join([f"- {news['title']}: {news['summary']}" for news in all_news])
    if not news_summaries_text:
        news_summaries_text = "분석된 주요 뉴스가 없습니다."

    # 각 엔티티에 대해 개별적으로 LLM을 호출하여 분석을 수행합니다.
    full_entity_analysis = {}
    entities_to_analyze = _get_entities_to_analyze(state)
    print("  - [1단계] 개별 엔티티 분석 시작...")
    for entity_key in entities_to_analyze:
        print(f"    - '{entity_key}' 분석 중...")
        single_analysis = _generate_single_entity_analysis(state, entity_key)
        if single_analysis:
            full_entity_analysis[entity_key] = single_analysis
        else:
            full_entity_analysis[entity_key] = {
                "내용": f"{entity_key}에 대한 분석 생성에 실패했습니다.",
                "주가_반응": "데이터 분석 오류"
            }
            print(f"'{entity_key}' 분석에 실패하여 기본값으로 대체합니다.")
    
    if not full_entity_analysis:
        print("모든 엔티티 분석에 실패했습니다. 프로세스를 중단합니다.")
        return {}

    # 분석된 모든 내용을 바탕으로 요약 및 최종 투자 전략을 각각 생성합니다.
    print("  - [2단계] 브리핑 요약 생성 중...")
    briefing_summary = _generate_briefing_summary(state, full_entity_analysis, financial_health, news_summaries_text)
    
    print("  - [3단계] 최종 투자 전략 생성 중...")
    strategy_suggestion = _generate_strategy_suggestion(state, full_entity_analysis, financial_health, news_summaries_text)

    # 분석 결과를 종합하여 최종 리포트 객체를 만듭니다.
    final_report_structured = FinalReport(
        report_title=f"[오늘의 투자 브리핑] {target_name} 기업 관련 주요 동향 및 전략",
        briefing_summary=briefing_summary if briefing_summary else "분석 요약 생성에 실패했습니다.",
        news_analysis={"entity_analysis": full_entity_analysis},
        strategy_suggestion=strategy_suggestion if strategy_suggestion else "전략 제안 생성에 실패했습니다."
    )
    
    print("[Report Synthesizer] 개별 호출 기반 최종 브리핑 생성을 완료했습니다.")
    return {"final_report": final_report_structured}
