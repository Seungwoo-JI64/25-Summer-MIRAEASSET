# analysis_model/agents/market_correlation_agent.py

import pandas as pd
from typing import Dict, Any, List, Set

from ..state import AnalysisState, MarketAnalysisResult, NewsImpactData, TickerPriceData
from .data_prep_agent import supabase_client
from .news_analyst_agent import METRICS_MAP

def get_correlation_text(kor_name: str, metric_name: str, corr_value: float) -> str:
    """상관계수 값에 따라 해석을 담은 텍스트를 생성하는 함수"""
    if corr_value is None:
        return f"'{kor_name}'과(와) '{metric_name}'의 상관관계 데이터가 없습니다."
    corr_value = round(corr_value, 2)
    if corr_value > 0.7: relation_text = "매우 강한 양의 관계"
    elif corr_value > 0.3: relation_text = "어느 정도 뚜렷한 양의 관계"
    elif corr_value > -0.3: relation_text = "거의 관계가 없거나 매우 약한 관계"
    elif corr_value > -0.7: relation_text = "어느 정도 뚜렷한 음의 관계"
    else: relation_text = "매우 강한 음의 관계"
    return f"'{kor_name}'과(와) '{metric_name}'의 상관계수는 {corr_value}로, '{relation_text}'를 보입니다."

def get_stock_data_from_supabase(ticker: str, start_date_str: str, end_date_str: str) -> pd.DataFrame | None:
    """Supabase DB에서 특정 기간의 시계열 데이터를 조회합니다."""
    print(f"  - Supabase에서 '{ticker}' 데이터 조회 (기간: {start_date_str} ~ {end_date_str})")
    
    table_name, time_col, price_col, ticker_col = "", "time", "close_price", "ticker"

    # ▼▼▼▼▼▼▼▼▼▼ 수정된 부분 ▼▼▼▼▼▼▼▼▼▼
    # 티커 종류에 따라 테이블과 컬럼 이름을 결정합니다.
    # Yahoo Finance 규칙에 따라 환율(=X)과 지수(^)는 financial_indices 테이블을 사용합니다.
    if ticker.startswith('^') or ticker.endswith('=X'):
        table_name = "financial_indices"
        time_col = "date"
        price_col = "value"
        ticker_col = "index_en"
    # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
    elif ticker.replace('.KS', '').isdigit():
        table_name = "korean_stocks"
    else:
        table_name = "us_stocks"

    try:
        res = supabase_client.table(table_name).select(f"{time_col}, {price_col}").eq(ticker_col, ticker).gte(time_col, start_date_str).lte(time_col, end_date_str).order(time_col, desc=False).execute()
        if not res.data:
            print(f"    - DB에 해당 기간의 '{ticker}' 데이터가 없습니다.")
            return None
        df = pd.DataFrame(res.data)
        df.rename(columns={price_col: 'price', time_col: 'time'}, inplace=True)
        df['time'] = pd.to_datetime(df['time']).dt.tz_convert('Asia/Seoul')
        return df
    except Exception as e:
        print(f"    ⚠️ Supabase에서 '{ticker}' 데이터 조회 중 오류: {e}")
        return None

def run_market_correlation(state: AnalysisState) -> Dict[str, Any]:
    print("\n--- 📈 시장 상관관계 및 뉴스 영향 분석 에이전트 실행 ---")
    
    target_ticker = state.get("ticker")
    target_name = state.get("company_name")
    selected_news = state.get("selected_news", [])
    selected_domestic_news = state.get("selected_domestic_news", [])

    if not all([target_ticker, target_name]):
        return {}

    # 1. 상관관계 분석 (해외 + 국내 뉴스 티커 모두 취합)
    all_related_metrics: Set[str] = set()
    for news in selected_news:
        all_related_metrics.update(news.get("related_metrics", []))
    for news in selected_domestic_news:
        all_related_metrics.update(news.get("related_metrics", []))
    
    print(f"분석 대상 전체 고유 지표: {all_related_metrics}")
    
    ticker_to_name_map = {target_ticker: target_name, **{t: i['name'] for t, i in METRICS_MAP.items()}}
    correlation_summary: List[str] = []
    for metric_ticker in all_related_metrics:
        metric_name = ticker_to_name_map.get(metric_ticker, metric_ticker)
        correlation = None
        try:
            # .single()은 0개 또는 2개 이상의 행이 반환되면 오류를 발생시키므로, 예외 처리를 강화합니다.
            if metric_ticker.startswith('^') or metric_ticker.endswith('=X'):
                res = supabase_client.table("correlation_kor_index").select("correlation").eq("ticker", target_ticker).eq("index_en", metric_ticker).execute()
                if res.data: correlation = res.data[0].get("correlation")
            else:
                res = supabase_client.table("correlation_kor_us").select("correlation").eq("korean_ticker", target_ticker).eq("us_ticker", metric_ticker).execute()
                if res.data: correlation = res.data[0].get("correlation")
            summary_text = get_correlation_text(target_name, metric_name, correlation)
            correlation_summary.append(summary_text)
        except Exception as e:
            print(f"⚠️ '{metric_ticker}' 상관관계 조회 중 오류 발생: {e}")
            correlation_summary.append(get_correlation_text(target_name, metric_name, None))

    # 2. 뉴스 블록별 주가 데이터 수집
    all_news = selected_news + selected_domestic_news
    if not all_news:
        return {"market_analysis_result": {"correlation_summary": correlation_summary, "news_impact_data": []}}
        
    sorted_news = sorted(all_news, key=lambda x: x['publish_date'])
    
    news_blocks: List[List[Dict]] = []
    current_block = [sorted_news[0]]
    for i in range(1, len(sorted_news)):
        prev_date = pd.to_datetime(current_block[-1]['publish_date'])
        curr_date = pd.to_datetime(sorted_news[i]['publish_date'])
        if (curr_date - prev_date).days <= 7:
            current_block.append(sorted_news[i])
        else:
            news_blocks.append(current_block)
            current_block = [sorted_news[i]]
    news_blocks.append(current_block)

    news_impact_data: List[NewsImpactData] = []
    for block in news_blocks:
        block_start_date = pd.to_datetime(block[0]['publish_date'])
        block_end_date = pd.to_datetime(block[-1]['publish_date'])
        fetch_start_date = (block_start_date - pd.DateOffset(days=7)).strftime('%Y-%m-%d')
        fetch_end_date = (block_end_date + pd.DateOffset(days=7)).strftime('%Y-%m-%d')
        
        block_tickers = {target_ticker}.union(*(set(n.get("related_metrics", [])) for n in block))
        block_titles = [n['title'] for n in block]
        
        price_data_by_name: Dict[str, TickerPriceData] = {}
        for ticker in block_tickers:
            df = get_stock_data_from_supabase(ticker, fetch_start_date, fetch_end_date)
            if df is not None and not df.empty:
                prices_list = [[row['time'].isoformat(), row['price']] for _, row in df.iterrows()]
                change_summary = "데이터 부족"
                if len(df['price']) > 1:
                    start_price, end_price = df['price'].iloc[0], df['price'].iloc[-1]
                    percentage_change = ((end_price - start_price) / start_price) * 100
                    change_text = "상승" if percentage_change >= 0 else "하락"
                    period_days = (df['time'].iloc[-1].date() - df['time'].iloc[0].date()).days + 1
                    change_summary = f"{period_days}일간 약 {abs(percentage_change):.2f}% {change_text}했습니다."
                
                name = ticker_to_name_map.get(ticker, ticker)
                price_data_by_name[name] = {"ticker": ticker, "prices": prices_list, "change_summary": change_summary}
        
        if price_data_by_name:
            news_impact_data.append({
                "news_titles": block_titles, "start_date": fetch_start_date,
                "end_date": fetch_end_date, "price_data_by_name": price_data_by_name
            })

    final_result: MarketAnalysisResult = {
        "correlation_summary": correlation_summary, "news_impact_data": news_impact_data
    }
    return {"market_analysis_result": final_result}
