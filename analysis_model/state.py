# 이 파일은 각 에이전트끼리의 원활한 통신을 위하여 미리 class를 지정한 것이다.
# 각 에이전트는 이 구조를 기반으로 데이터를 주고받으며,
# 상태를 업데이트합니다.
# 이 구조는 LangGraph의 상태 관리 기능을 활용하여
# 파이프라인의 각 단계에서 데이터를 효율적으로 처리할 수 있도록 돕습니다.

from __future__ import annotations
from typing import TypedDict, List, Dict, Any

# LangGraph는 상태 객체의 필드가 변경될 때마다 전체 객체를 복사하는 것이 아니라
# 변경된 필드만 효율적으로 업데이트합니다.
# 각 필드에 `| None`을 추가하여 Optional로 만들면,
# 파이프라인 초기 단계에서 아직 채워지지 않은 필드가 있어도 오류가 발생하지 않습니다.
# 각 에이전트는 자신의 작업이 끝난 후 해당하는 필드를 채워넣게 됩니다.



# 아래의 class는 데이터를 어떻게 구성해야하는지에 대한 설계도이다.
class SelectedNews(TypedDict):
    """뉴스 분석 에이전트가 선별한 개별 뉴스 정보를 담는 구조"""
    title: str  # 뉴스 제목
    url: str    # 뉴스 원문 URL
    summary: str # 뉴스 요약
    entities: List[str] # 뉴스에서 추출된 핵심 엔티티 (예: 'SK하이닉스', 'SOX 지수')
    related_metrics: List[str] # 엔티티의 Ticker

class MarketAnalysisResult(TypedDict):
    """시장 상관관계 분석 결과를 담는 구조"""
    correlation_coefficient: float # 상관계수
    analysis_caption: str      # 분석 결과에 대한 캡션
    chart_image_path: str      # 생성된 차트 이미지 파일의 경로

class FinalReport(TypedDict):
    """최종 보고서의 구조"""
    title: str                  # 리포트 제목
    executive_summary: str      # 핵심 요약
    key_findings: List[Dict[str, Any]] # 분석 근거 (뉴스, 차트 등)
    outlook: str                # 종합 전망


# 모든 데이터는 AnalysisState라는 하나의 상태 객체에 담겨
# LangGraph의 파이프라인을 통해 전달됩니다.
class AnalysisState(TypedDict):
    """전체 분석 파이프라인의 상태를 관리하는 중앙 데이터 객체"""
    company_name: str | None # 기업 이름
    ticker: str | None       # 주식 티커 (예: 000660.KS)
    company_description: str | None   # 기업 개요 (예: 메모리 반도체 전문 기업...)
    financial_health: str | None # 재무 건전성 분석 결과

    selected_news: List[SelectedNews] | None # 뉴스 분석 에이전트가 채우는 필드
    market_analysis_result: MarketAnalysisResult | None # 시장 상관관계 분석 에이전트가 채우는 필드
    final_report: FinalReport | None # 최종 보고서 생성 에이전트가 채우는 필드
