#################################
# 2. 시장 데이터 상관관계 분석 에이전트

# 미리 생성된 지수간의 상관관계를 가져옵니다.
# 앞서 추출한 뉴스의 시점 전후로 두가에 어떠한 변동이 있는지
# 보고자 하는 기업과 미국 기업, 인덱스에 대해 
# 시각화를 진행합니다.

import os
import time
from typing import Dict, Any, List
import yfinance as yf
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 상위 폴더에 있는 state.py 모듈에서 AnalysisState 클래스를 가져옵니다.
from ..state import AnalysisState, MarketAnalysisResult, SelectedNews




# --- Matplotlib 한글 폰트 설정 ---
try:
    font_path = "AppleGothic.ttf" # Mac 사용자
    font_prop = fm.FontProperties(fname=font_path, size=10)
    plt.rc('font', family=fm.FontProperties(fname=font_path).get_name())
except FileNotFoundError:
    try:
        font_path = "C:/Windows/Fonts/malgun.ttf" # Windows 사용자
        font_prop = fm.FontProperties(fname=font_path, size=10)
        plt.rc('font', family=fm.FontProperties(fname=font_path).get_name())
    except FileNotFoundError:
        print("⚠️ [Market Correlation] 한글 폰트를 찾을 수 없어 기본 폰트로 설정됩니다. 차트의 한글이 깨질 수 있습니다.")
        font_prop = fm.FontProperties(size=10)

plt.rcParams['axes.unicode_minus'] = False




# --- 상관관계 자료 불러오는 함수 ---
## supabase에서 미리 계산된 상관계수를 불러옵니다.
def get_precalculated_correlation_from_db(target_ticker: str, related_ticker: str) -> float | None:
    """
    미리 계산되어 저장된 상관계수 값을 Supabase  DB에서 조회하는 함수.
    """
    print(f"[Market Correlation] DB에서 '{target_ticker}'와 '{related_ticker}'의 사전 계산된 상관계수를 조회합니다.")
    return .get((target_ticker, related_ticker))

# --- 주가 데이터를 불러오는 함수 ---
## supabase에서 미리 수집된 주가를 불러옵니다.
def get_stock_data_from_supabase(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    Supabase DB에 저장된 3년치 주가 데이터 중, 특정 기간의 데이터를 조회한다고 가정하는 함수.
    """
    print(f"📈 [Market Correlation] Supabase DB에서 티커 {tickers}의 데이터를 조회합니다. (기간: {start_date} ~ {end_date})")
    # 데모를 위해 yfinance를 사용하여 해당 기간의 데이터를 가져오는 것으로 시뮬레이션합니다.
    try:
        data = yf.download(tickers, start=start_date, end=end_date)['Adj Close']
        if data.empty:
            print(f"⚠️ [Market Correlation] Supabase에서 해당 기간의 데이터를 가져오지 못했습니다.")
            return None
        return data.dropna()
    except Exception as e:
        print(f"데이터 조회 중 에러 발생: {e}")
        return None
    


# --- 주가 시각화 함수 ---
## 어떻게 시각화를 할지 정하지 않았기에 아래의 함수는 사용하지 않는다    
def create_correlation_chart(
    data: pd.DataFrame,
    target_ticker: str,
    related_ticker: str,
    target_name: str,
    related_name: str,
    precalculated_correlation: float,
    save_path: str
):
    """두 자산의 주가 추이와 '미리 계산된' 상관계수를 포함한 차트를 생성하고 저장합니다."""
    print(f"🎨 [Market Correlation] '{target_name}'와 '{related_name}'의 상관관계 차트를 생성합니다.")
    
    scaler = MinMaxScaler()
    scaled_data = pd.DataFrame(scaler.fit_transform(data), columns=data.columns, index=data.index)

    plt.figure(figsize=(10, 5))
    plt.plot(scaled_data.index, scaled_data[target_ticker], label=f'{target_name} (정규화)')
    plt.plot(scaled_data.index, scaled_data[related_ticker], label=f'{related_name} (정규화)')
    
    chart_title = f"{target_name} vs {related_name} 주가 추이 (뉴스 발생일 이전 1년)"
    plt.title(chart_title, fontproperties=font_prop)
    plt.xlabel('날짜', fontproperties=font_prop)
    plt.ylabel('정규화된 주가', fontproperties=font_prop)
    plt.legend(prop=font_prop)
    plt.grid(True)
    
    plt.text(0.05, 0.95, f'3년 상관계수 (사전 계산): {precalculated_correlation:.2f}', transform=plt.gca().transAxes,
             fontsize=12, verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5))

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"✅ [Market Correlation] 차트가 '{save_path}'에 저장되었습니다.")




    # --- 에이전트 실행 함수 ---
def run_market_correlation(state: AnalysisState) -> Dict[str, Any]:
    """
    미리 계산된 상관계수를 DB에서 조회하고, 뉴스 시점 이전 1년간의 데이터를 기반으로 시각적 증거(차트)를 생성합니다.
    """
    print("\n--- 📈 시장 상관관계 분석 에이전트 실행 ---")
    target_ticker = state.get("ticker")
    target_name = state.get("company_name")
    selected_news = state.get("selected_news")

    if not all([target_ticker, target_name, selected_news]):
        print("⚠️ [Market Correlation] 분석에 필요한 데이터가 부족합니다.")
        return {}

    first_news = selected_news[0]
    related_tickers = first_news.get("related_metrics")
    
    # 중요: news_data.py와 state.py의 SelectedNews에 'date' 필드가 추가되었다고 가정합니다.
    # 예: "date": "2024-07-10"
    news_date_str = first_news.get("date")

    if not related_tickers or not news_date_str:
        print("⚠️ [Market Correlation] 뉴스에 연관된 지표 또는 날짜가 없어 분석을 건너뜁니다.")
        return {}
    
    related_ticker = related_tickers[0]

    # 1. DB에서 미리 계산된 3년치 상관계수 조회
    correlation_coefficient = get_precalculated_correlation_from_db(target_ticker, related_ticker)
    if correlation_coefficient is None:
        print(f"⚠️ [Market Correlation] DB에 '{target_ticker}'와 '{related_ticker}'의 상관계수 데이터가 없습니다.")
        return {}

    # 2. 뉴스 날짜를 기준으로 시각화할 기간 설정 (뉴스 발생일 이전 1년)
    news_date = pd.to_datetime(news_date_str)
    end_date = (news_date + pd.DateOffset(days=1)).strftime('%Y-%m-%d') # 당일 데이터 포함
    start_date = (news_date - pd.DateOffset(years=1)).strftime('%Y-%m-%d')

    # 3. Supabase DB에서 해당 기간의 주가 데이터 조회
    stock_data_for_chart = get_stock_data_from_supabase([target_ticker, related_ticker], start_date, end_date)
    
    if stock_data_for_chart is None or stock_data_for_chart.shape[1] < 2:
        print("⚠️ [Market Correlation] 차트 생성을 위한 주가 데이터를 가져오지 못해 시각화 단계를 건너뜁니다.")
        chart_save_path = None
    else:
        # 4. 차트 생성 및 저장
        chart_save_path = f"charts/{target_ticker}_vs_{related_ticker}_around_{news_date_str}.png"
        related_name = first_news["entities"][0] if first_news["entities"] else related_ticker
        create_correlation_chart(
            data=stock_data_for_chart,
            target_ticker=target_ticker,
            related_ticker=related_ticker,
            target_name=target_name,
            related_name=related_name,
            precalculated_correlation=correlation_coefficient,
            save_path=chart_save_path
        )

    # 5. 분석 결과 캡션 생성
    caption = (
        f"3년간의 데이터를 기반으로 사전 계산된 '{target_name}'과 '{related_name}'의 상관계수는 {correlation_coefficient:.2f}입니다. "
        f"이는 두 자산이 {'강한 양의 관계' if correlation_coefficient > 0.7 else '어느 정도의 양의 관계' if correlation_coefficient > 0.3 else '거의 무관한 관계' if correlation_coefficient > -0.3 else '어느 정도의 음의 관계' if correlation_coefficient > -0.7 else '강한 음의 관계'}에 있음을 의미합니다. "
        f"'{first_news['title']}' 뉴스({news_date_str}) 발생 이전 1년간의 주가 추이에서도 이러한 연관성을 확인할 수 있습니다."
    )

    # 6. 최종 결과 구성
    analysis_result: MarketAnalysisResult = {
        "correlation_coefficient": correlation_coefficient,
        "analysis_caption": caption,
        "chart_image_path": chart_save_path,
    }

    return {"market_analysis_result": analysis_result}