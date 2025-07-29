# analysis_model/state.py
# 이 파일은 각 에이전트끼리의 원활한 통신을 위하여 미리 class를 지정한 것이다.
# 각 에이전트는 이 구조를 기반으로 데이터를 주고받으며,
# 상태를 업데이트합니다.
# 이 구조는 LangGraph의 상태 관리 기능을 활용하여
# 파이프라인의 각 단계에서 데이터를 효율적으로 처리할 수 있도록 돕습니다.

from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional

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
    publish_date: str # 날짜 필드 (published_date -> publish_date로 통일성을 위해 수정)
    entities: List[str] # 뉴스에서 추출된 핵심 엔티티 (예: 'SK하이닉스', 'SOX 지수')
    related_metrics: List[str] # 엔티티의 Ticker

class DomesticNews(TypedDict):
    """국내 뉴스 분석 에이전트가 선별한 개별 뉴스 정보"""
    title: str
    url: str
    summary: str
    publish_date: str
    entities: List[str]         # 뉴스에서 추출된 핵심 엔티티
    related_metrics: List[str]  # 엔티티의 Ticker

class TickerPriceData(TypedDict):
    """개별 티커의 시계열 데이터와 요약 정보"""
    ticker: str
    # [[타임스탬프, 가격], [타임스탬프, 가격], ...] 형태
    prices: List[List[Any]]
    change_summary: str # 예: '15일간 약 3.5% 상승했습니다.'

class NewsImpactData(TypedDict):
    """뉴스 이벤트 '블록'과 관련된 주체들의 주가 변동 데이터를 담는 구조"""
    news_titles: List[str]
    start_date: str
    end_date: str
    # {'Apple': TickerPriceData, 'Samsung': TickerPriceData, ...} 형태
    price_data_by_name: Dict[str, TickerPriceData]

class MarketAnalysisResult(TypedDict):
    """시장 상관관계 및 뉴스 영향 분석 결과를 담는 구조"""
    correlation_summary: List[str]
    news_impact_data: List[NewsImpactData]
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] # <--- 추가: 상관관계 매트릭스

class PerEntityAnalysis(TypedDict):
    """개별 주체(기업/지수)에 대한 분석 내용"""
    내용: str
    주가_반응: str

class NewsAnalysis(TypedDict):
    """뉴스 분석 결과 (개별 주체 분석 포함)"""
    # {'Apple(AAPL)': PerEntityAnalysis, ...} 형태
    entity_analysis: Dict[str, PerEntityAnalysis]

class FinalReport(TypedDict):
    """최종 생성된 '개장 전 투자 브리핑'의 구조"""
    report_title: str
    briefing_summary: str
    company_ko_description: str # 🚨 NEW: ko_summary를 위한 필드 추가
    news_analysis: NewsAnalysis
    strategy_suggestion: str

# 모든 데이터는 AnalysisState라는 하나의 상태 객체에 담겨
# LangGraph의 파이프라인을 통해 전달됩니다.
class AnalysisState(TypedDict):
    """전체 분석 파이프라인의 상태를 관리하는 중앙 데이터 객체"""
    ticker: str | None
    company_name: str | None # UI 표시용 이름 (한국어 가능)
    company_description: str | None # 영문 요약 (LLM 프롬프트용)
    ko_company_description: str | None # 🚨 NEW: ko_summary를 위한 필드
    financial_health: str | None
    selected_news: List[SelectedNews] | None           # 해외 뉴스
    selected_domestic_news: List[DomesticNews] | None  # 국내 뉴스
    market_analysis_result: MarketAnalysisResult | None
    final_report: FinalReport | None

    # --- 그래프 시각화를 위해 추가된 필드 ---
    historical_prices: Optional[Dict[str, List[Dict[str, Any]]]] # 티커별 {'date': 'YYYY-MM-DD', 'close': float} 리스트
    news_event_markers: Optional[Dict[str, List[str]]] # 티커별 뉴스 발생 날짜 리스트 {'AAPL': ['YYYY-MM-DD', ...]}
    all_analyzed_tickers: Optional[List[str]] # 분석 파이프라인에서 다룬 모든 관련 티커 목록 (AAPL, NVDA, ^NDX, USDKRW=X 등)