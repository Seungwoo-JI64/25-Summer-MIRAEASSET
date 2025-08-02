#################################
# 3. 시장 데이터 분석 에이전트

import pandas as pd
from typing import Dict, Any, List, Set
from datetime import datetime, timedelta

from ..state import AnalysisState, MarketAnalysisResult, NewsImpactData, TickerPriceData
from .data_prep_agent import supabase_client
from .news_analyst_agent import METRICS_MAP # 뉴스 분석 에이전트에서 METRICS_MAP 파일 불러오기

################################
# 상관관계 설명 함수
## 본 분석에서는 더이상 사용하지 않음
### 코드의 연속성을 위해 작동은 하도록 한다
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

################################
# 데이터베이스에서 주식 데이터를 조회하는 함수
def get_stock_data_from_supabase(ticker: str, start_date_str: str, end_date_str: str) -> pd.DataFrame | None:
    """Supabase DB에서 특정 기간의 시계열 데이터를 조회합니다."""
    
    table_name, time_col, price_col, ticker_filter_col = "", "time", "close_price", "ticker" # Default values

    if ticker.startswith('^') or ticker.endswith('=X'): # 주요지표
        table_name = "financial_indices"
        time_col = "date"
        price_col = "value"
        ticker_filter_col = "index_en"
    elif ticker.endswith('.KS') or ticker.endswith('.KQ'): # 한국 기업 주식
        table_name = "korean_stocks"
        time_col = "time"
        price_col = "close_price"
        ticker_filter_col = "ticker"
    else: # 미국 기업 주식
        table_name = "us_stocks"
        time_col = "time"
        price_col = "close_price"
        ticker_filter_col = "ticker"

    try:
        # 데이터 추출
        res = supabase_client.table(table_name).select(f"{time_col}, {price_col}").eq(ticker_filter_col, ticker).gte(time_col, start_date_str).lte(time_col, end_date_str).order(time_col, desc=False).execute()
        
        if not res.data:
            return None
            
        df = pd.DataFrame(res.data)
        df.rename(columns={price_col: 'close', time_col: 'date'}, inplace=True) 

        df['date'] = pd.to_datetime(df['date']).dt.date
        df['date'] = df['date'].astype(str)

        df.drop_duplicates(subset=['date'], keep='last', inplace=True)

        return df
    except Exception as e:
        print(f"    ⚠️ Supabase에서 '{ticker}' 데이터 조회 중 오류: {e}")
        return None

################################
# 상관관계 계산
def run_market_correlation(state: AnalysisState) -> Dict[str, Any]:
    print("\n--- 📈 시장 상관관계 및 뉴스 영향 분석 에이전트 실행 ---")
    
    target_ticker = state.get("ticker")
    target_name = state.get("company_name")
    selected_news = state.get("selected_news", [])
    selected_domestic_news = state.get("selected_domestic_news", [])

    if not all([target_ticker, target_name]):
        print("    ⚠️ 티커 또는 회사 이름이 없어 시장 상관관계 분석을 건너뜜.")
        return {}

    # 분석에 사용할 티커와 뉴스 개시 날짜 가져오기
    all_analyzed_tickers: Set[str] = set()
    news_event_markers_detailed: Dict[str, Dict[str, List[Dict[str, str]]]] = {}

    all_analyzed_tickers.add(target_ticker)

    for news_list in [selected_news, selected_domestic_news]:
        if news_list:
            for news_item in news_list:
                news_date = news_item.get("published_date") or news_item.get("publish_date")
                if news_date:
                    news_date_str = pd.to_datetime(news_date).strftime('%Y-%m-%d')
                    
                    # 뉴스 상세 정보 딕셔너리 생성
                    news_details = {
                        "title": news_item.get("title", "제목 없음"),
                        "url": news_item.get("url", "#"),
                        "date": news_date_str
                    }

                    # 관련 티커에 뉴스 정보 추가
                    if news_item.get("related_metrics"):
                        for ticker in news_item["related_metrics"]:
                            all_analyzed_tickers.add(ticker)
                            news_event_markers_detailed.setdefault(ticker, {}).setdefault(news_date_str, []).append(news_details)
                    # 대상 티커에도 뉴스 정보 추가
                    news_event_markers_detailed.setdefault(target_ticker, {}).setdefault(news_date_str, []).append(news_details)
    
    # 중복 뉴스 제거 (동일 티커, 동일 날짜, 동일 URL 기준)
    cleaned_news_event_markers = {}
    for ticker, dates_dict in news_event_markers_detailed.items():
        cleaned_news_event_markers[ticker] = {}
        for date_str, news_items in dates_dict.items():
            # (title, url) 튜플을 사용하여 중복 제거
            unique_news_tuples = { (item['title'], item['url']) for item in news_items }
            # 원본 딕셔너리 형태로 다시 변환
            cleaned_news_items = [{"title": t, "url": u, "date": date_str} for t, u in unique_news_tuples]
            cleaned_news_event_markers[ticker][date_str] = cleaned_news_items
    
    print(f"분석 대상 전체 고유 지표: {all_analyzed_tickers}")
    
    # 장기 주식 데이터 조회 (최대 2년)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 2)
    fetch_start_date_str = start_date.strftime('%Y-%m-%d')
    fetch_end_date_str = end_date.strftime('%Y-%m-%d')

    historical_prices_data: Dict[str, List[Dict[str, Any]]] = {}
    for ticker in all_analyzed_tickers:
        df = get_stock_data_from_supabase(ticker, fetch_start_date_str, fetch_end_date_str)
        if df is not None and not df.empty:
            historical_prices_data[ticker] = df.to_dict(orient='records')
        else:
            print(f"    -> '{ticker}'의 시계열 데이터를 가져오지 못했습니다.")

    # 상관관계 매트릭스 계산
    ## 최종 보고서 LLM에서 사용할 예정
    correlation_matrix_data: Dict[str, Dict[str, float]] = {}
    if len(all_analyzed_tickers) > 1:
        df_all_prices = pd.DataFrame()
        for ticker, data_list in historical_prices_data.items():
            if data_list:
                df_temp = pd.DataFrame(data_list)
                df_temp['date'] = pd.to_datetime(df_temp['date'])
                df_temp = df_temp.set_index('date')['close'].rename(ticker)
                df_all_prices = pd.concat([df_all_prices, df_temp], axis=1)
        
        df_all_prices = df_all_prices.ffill().bfill()
        
        if not df_all_prices.empty and len(df_all_prices.columns) > 1:
            correlation_matrix_data = df_all_prices.corr().to_dict(orient='index')
        else:
            print("    ⚠️ 상관관계 매트릭스를 계산할 충분한 데이터가 없습니다.")

    # 상관관계 설명 추가
    ticker_to_name_map = {target_ticker: target_name, **{t: i['name'] for t, i in METRICS_MAP.items()}}
    correlation_summary: List[str] = []
    _all_related_metrics_for_summary: Set[str] = set()
    for news in selected_news:
        _all_related_metrics_for_summary.update(news.get("related_metrics", []))
    for news in selected_domestic_news:
        _all_related_metrics_for_summary.update(news.get("related_metrics", []))

    for metric_ticker in _all_related_metrics_for_summary:
        metric_name = ticker_to_name_map.get(metric_ticker, metric_ticker)
        correlation = None
        try:
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

    #####################################
    # 뉴스 블록 기간 생성
    ## 일주일 단위로 뉴스를 묶고 전후 7일간의 주식 데이터를 조회
    all_news = (selected_news) + (selected_domestic_news)
    news_impact_data: List[NewsImpactData] = []
    
    # 뉴스 블록 생성
    if all_news:
        sorted_news = sorted(all_news, key=lambda x: x.get('publish_date') or x.get('published_date'))
        news_blocks: List[List[Dict]] = []
        if sorted_news:
            current_block = [sorted_news[0]]
            for i in range(1, len(sorted_news)):
                prev_date = pd.to_datetime(current_block[-1].get('publish_date') or current_block[-1].get('published_date'))
                curr_date = pd.to_datetime(sorted_news[i].get('publish_date') or sorted_news[i].get('published_date'))
                if (curr_date - prev_date).days <= 7: #7일 단위
                    current_block.append(sorted_news[i])
                else:
                    news_blocks.append(current_block)
                    current_block = [sorted_news[i]]
            news_blocks.append(current_block)

        # 뉴스 기간 생성
        for block in news_blocks:
            block_dates = [pd.to_datetime(n.get('publish_date') or n.get('published_date')).date() for n in block]
            block_start_raw, block_end_raw = min(block_dates), max(block_dates)
            fetch_start_date = (datetime.combine(block_start_raw, datetime.min.time()) - timedelta(days=7)).strftime('%Y-%m-%d')
            fetch_end_date = (datetime.combine(block_end_raw, datetime.min.time()) + timedelta(days=7)).strftime('%Y-%m-%d')
            block_tickers = {target_ticker}.union(*(set(n.get("related_metrics", [])) for n in block))
            block_titles = [n['title'] for n in block]
            
            price_data_by_name: Dict[str, TickerPriceData] = {}
            for ticker in block_tickers:
                df = get_stock_data_from_supabase(ticker, fetch_start_date, fetch_end_date)
                if df is not None and not df.empty:
                    prices_list = [[row['date'], row['close']] for _, row in df.iterrows()]
                    change_summary = "데이터 부족"
                    if len(df['close']) > 1: # 해당 기간 주식의 변동을 상승과 하락으로 요약
                        start_price, end_price = df['close'].iloc[0], df['close'].iloc[-1]
                        percentage_change = ((end_price - start_price) / start_price) * 100 if start_price != 0 else 0
                        change_text = "상승" if percentage_change >= 0 else "하락"
                        period_days = (pd.to_datetime(df['date'].iloc[-1]).date() - pd.to_datetime(df['date'].iloc[0]).date()).days + 1
                        change_summary = f"{period_days}일간 약 {abs(percentage_change):.2f}% {change_text}했습니다."
                    
                    name = ticker_to_name_map.get(ticker, ticker)
                    price_data_by_name[name] = {"ticker": ticker, "prices": prices_list, "change_summary": change_summary}
            
            if price_data_by_name:
                news_impact_data.append({
                    "news_titles": block_titles, "start_date": fetch_start_date,
                    "end_date": fetch_end_date, "price_data_by_name": price_data_by_name
                })

    # 단기 주식 변동 그래프를 위한 데이터 가공
    ## 시각화를 위함
    ### 뉴스 블록 기간을 사용
    short_term_prices: Dict[str, List[Dict[str, Any]]] = {}
    temp_short_term_data: Dict[str, Dict[str, float]] = {}

    for impact_item in news_impact_data:
        for name, price_data in impact_item.get("price_data_by_name", {}).items():
            ticker = price_data["ticker"]
            if ticker not in temp_short_term_data:
                temp_short_term_data[ticker] = {}
            
            for date, close_price in price_data["prices"]:
                temp_short_term_data[ticker][date] = close_price

    for ticker, date_price_map in temp_short_term_data.items():
        # 날짜순으로 정렬하여 리스트로 변환
        sorted_prices = sorted(date_price_map.items())
        short_term_prices[ticker] = [{"date": date, "close": price} for date, price in sorted_prices]

    final_market_result: MarketAnalysisResult = {
        "correlation_summary": correlation_summary,
        "news_impact_data": news_impact_data,
        "correlation_matrix": correlation_matrix_data
    }
    
    print("시장 상관관계 및 뉴스 영향 분석 완료.")
    return {
        "market_analysis_result": final_market_result,
        "historical_prices": historical_prices_data, # 장기 주식 데이터
        "short_term_prices": short_term_prices, # 단기 주식 데이터
        "news_event_markers": cleaned_news_event_markers,
        "all_analyzed_tickers": list(all_analyzed_tickers)
    }