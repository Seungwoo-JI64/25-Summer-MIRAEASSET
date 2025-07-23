# 프로젝트를 실행하는 메인 파트
## 여러 에이전트들을 LangGraph를 이용하여 하나로 묶는다

import os
import json
from pprint import pprint
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# --- 프로젝트 구성 요소 임포트 ---

# .env 파일에서 API 키 등 환경 변수를 로드합니다.
# 이 코드는 프로젝트 루트에 .env 파일이 있다고 가정합니다.
load_dotenv()

# 각 단계별 에이전트의 실행 함수를 가져옵니다.
from state import AnalysisState
from agents.data_prep_agent import run_data_prep
from agents.news_analyst_agent import run_news_analyst
from agents.market_correlation_agent import run_market_correlation
from agents.report_synthesizer_agent import run_report_synthesizer

# --- LangGraph 워크플로우 정의 ---

# 1. 그래프 객체 생성
# StateGraph에 AnalysisState를 연결하여, 그래프의 모든 상태가 AnalysisState의 구조를 따르도록 정의합니다.
workflow = StateGraph(AnalysisState)

# 2. 노드(Node) 추가
# 각 에이전트의 실행 함수를 그래프의 노드로 추가합니다.
# 각 노드는 state를 입력받아 작업 후, 변경된 state의 일부를 반환합니다.
workflow.add_node("data_prep", run_data_prep)
workflow.add_node("news_analyst", run_news_analyst)
workflow.add_node("market_correlation", run_market_correlation)
workflow.add_node("report_synthesizer", run_report_synthesizer)

# 3. 엣지(Edge) 연결
# 작업이 진행될 순서대로 노드들을 연결합니다.
workflow.add_edge("data_prep", "news_analyst")
workflow.add_edge("news_analyst", "market_correlation")
workflow.add_edge("market_correlation", "report_synthesizer")

# 4. 진입점 및 종료점 설정
workflow.set_entry_point("data_prep")
workflow.add_edge("report_synthesizer", END) # report_synthesizer 노드가 끝나면 전체 워크플로우가 종료됩니다.

# 5. 그래프 컴파일
# 정의된 워크플로우를 실행 가능한 애플리케이션으로 컴파일합니다.
app = workflow.compile()

# --- 파이프라인 실행 ---

if __name__ == "__main__":
    print("[Main] 인사이트링크 AI 금융 리포터 파이프라인을 시작합니다.")

    # 1. 분석을 시작할 기업 이름으로 초기 상태를 설정합니다.
    initial_state = {
        "company_name": "SK하이닉스" #여기에 내가 보기를 워하는 기업의 영문명을 입력한다.
    }

    # 2. 컴파일된 앱(app)에 초기 상태를 입력하여 파이프라인을 실행합니다.
    # .stream()을 사용하면 각 단계의 결과를 실시간으로 확인할 수 있습니다.
    final_state = None
    for s in app.stream(initial_state, {"recursion_limit": 10}):
        # s는 각 노드의 이름과 그 노드가 반환한 결과(딕셔너리)를 담고 있습니다.
        node_name = list(s.keys())[0]
        node_output = list(s.values())[0]
        print(f"--- [Main] '{node_name}' 노드 실행 완료 ---")
        # pprint(node_output) # 각 단계의 상세 결과 확인용
        final_state = s # 마지막 상태를 저장

    print("\n\n[Main] 모든 파이프라인 실행이 완료되었습니다.")
    print("=" * 50)
    print(" 최종 생성된 보고서 ".center(50, "="))
    print("=" * 50)

    # 3. 최종 상태에서 생성된 보고서를 추출하여 출력합니다.
    if final_state:
        final_report_data = final_state.get('report_synthesizer', {}).get('final_report')
        if final_report_data:
            # 보기 좋게 JSON 형식으로 출력
            print(json.dumps(final_report_data, indent=4, ensure_ascii=False))
        else:
            print("최종 보고서 데이터를 찾을 수 없습니다.")
    else:
        print("파이프라인 실행 중 오류가 발생했습니다.")

