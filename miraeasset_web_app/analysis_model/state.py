# analysis_model/state.py
# 이 파일은 각 에이전트끼리의 원활한 통신을 위하여 미리 class를 지정한 것
# 각 에이전트는 이 구조를 기반으로 데이터를 주고받으며 상태를 업데이트함
# LangChain 방식

from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional

# 아래의 class는 데이터를 어떻게 구성해야하는지에 대한 설계도이다.
class SelectedNews(TypedDict):
    """뉴스 분석 에이전트가 선별한 개별 뉴스 정보를 담는 구조"""
    title: str  # 뉴스 제목
    url: str    # 뉴스 원문 URL
    summary: str # 뉴스 요약
    publish_date: str # 날짜 필드
    entities: List[str] # 뉴스에서 추출된 핵심 엔티티 (예: 'SK하이닉스', 'SOX 지수')
    related_metrics: List[str] # 엔티티의 Ticker

class DomesticNews(TypedDict):
    """국내 뉴스 분석 에이전트가 선별한 개별 뉴스 정보"""
    title: str # 뉴스 제목
    url: str # 뉴스 원문 URL
    summary: str # 뉴스 요약
    publish_date: str # 날짜 필드
    entities: List[str] # 뉴스에서 추출된 핵심 엔티티 (예: 'SK하이닉스', 'SOX 지수')
    related_metrics: List[str] # 엔티티의 Ticker

class TickerPriceData(TypedDict):
    """개별 티커의 시계열 데이터와 요약 정보"""
    ticker: str # 티커목록
    prices: List[List[Any]] # [[타임스탬프, 가격], [타임스탬프, 가격], ...] 형태
    change_summary: str # 주식 변동 요약 / 예: '15일간 약 3.5% 상승했습니다.'

class NewsImpactData(TypedDict):
    """뉴스 이벤트 '블록'과 관련된 주체들의 주가 변동 데이터를 담는 구조"""
    news_titles: List[str] # 선택된 뉴스 제목
    start_date: str # 뉴스 블록 시작일
    end_date: str # 뉴스 블록 종료일
    price_data_by_name: Dict[str, TickerPriceData] # {'Apple': TickerPriceData, 'Samsung': TickerPriceData, ...} 형태

class MarketAnalysisResult(TypedDict):
    """
    시장 상관관계 및 뉴스 영향 분석 결과를 담는 구조
    더이상 사용하지 않음
    """
    correlation_summary: List[str] # 상관관계 요약
    news_impact_data: List[NewsImpactData] # 뉴스 엔티티별 주가 변동 데이터
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] # 상관관계 매트릭스

class PerEntityAnalysis(TypedDict):
    """
    개별 주체(기업/지수)에 대한 분석 내용
    더이상 사용하지 않음
    """
    내용: str
    주가_반응: str

class NewsAnalysis(TypedDict):
    """
    뉴스 분석 결과 (개별 주체 분석 포함)
    더이상 사용하지 않음
    """
    # {'Apple(AAPL)': PerEntityAnalysis, ...} 형태
    entity_analysis: Dict[str, PerEntityAnalysis] # 분석문

class FinalReport(TypedDict):
    """최종 생성된 최종 투자 브리핑의 구조"""
    report_title: str # 분석 제목
    briefing_summary: str # 분석문
    company_ko_description: str # 기업 설명문 한국어 번역본
    news_analysis: NewsAnalysis # 기업/지표 - 뉴스 분석문
    strategy_suggestion: str # 개인투자자 맞춤 전략



##################################################
# 모든 데이터를 관리하는 중앙 상태 객체
## 위에서 생성만 모든 객체는 여기에 입력되며, 각각의 AI에이전트를 통해 전달
class AnalysisState(TypedDict):
    """전체 분석 파이프라인의 상태를 관리하는 중앙 데이터 객체"""
    ticker: str | None # 분석 대상 티커
    company_name: str | None # UI 표시용 기업 이름 (한국어)
    company_description: str | None # 기업 영문 요약 (LLM 프롬프트용)
    ko_company_description: str | None # 기업 설명문 한국어 번역본 (최종 분석 보고서용)
    financial_health: str | None # 기업건전성 보고서
    selected_news: List[SelectedNews] | None # 선택된 해외 뉴스
    selected_domestic_news: List[DomesticNews] | None # 선택된 국내 뉴스
    market_analysis_result: MarketAnalysisResult | None # 주식 상관관계와 주가 데이터
    final_report: FinalReport | None # 최종 분석 보고서

    # 그래프 시각화를 위해 추가된 필드
    historical_prices: Optional[Dict[str, List[Dict[str, Any]]]] # 티커별 {'date': 'YYYY-MM-DD', 'close': float} 리스트
    news_event_markers: Optional[Dict[str, List[str]]] # 티커별 뉴스 발생 날짜 리스트 {'AAPL': ['YYYY-MM-DD', ...]}
    all_analyzed_tickers: Optional[List[str]] # 분석 파이프라인에서 다룬 모든 관련 티커 목록 (AAPL, NVDA, ^NDX, USDKRW=X 등)