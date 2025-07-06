import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timezone
from supabase import create_client, Client

# 지표 정보 (기존과 동일)
tickers_info = {
    '^GSPC': {'en': '^GSPC', 'ko': 'S&P 500 지수'},
    '^NDX': {'en': '^NDX', 'ko': '나스닥 100 지수'},
    '^DJI': {'en': '^DJI', 'ko': '다우존스 산업평균지수'},
    '^KS11': {'en': '^KS11', 'ko': '코스피 지수'},
    '^KQ11': {'en': '^KQ11', 'ko': '코스닥 지수'},
    'LIT': {'en': 'LIT', 'ko': '리튬 ETF'},
    '^TNX': {'en': 'TNX', 'ko': '미국 10년물 국채 수익률'},
    'NBI': {'en': 'NBI', 'ko': '나스닥 바이오테크놀로지 지수'},
    '^VIX': {'en': '^VIX', 'ko': 'CBOE 변동성 지수'},
    'CL=F': {'en': 'CL=F', 'ko': 'WTI 원유 선물'},
    'FDN': {'en': 'FDN', 'ko': '다우존스 인터넷 지수'},
    'USDKRW=X': {'en': 'USDKRW=X', 'ko': '달러/원 환율'}
}

# 모든 Ticker 한번에 불러오기 (최근 5일치 데이터 요청으로 주말/휴일 문제 해결)
tickers_list = list(tickers_info.keys())
data_wide = yf.download(tickers_list, period="5d", auto_adjust=True, progress=False)

# 데이터가 비어 있는지 확인 후 종료
if data_wide.empty:
    print("Downloaded data is empty. Exiting.")
    exit()

# '종가(Close)' 데이터 추출 후, 모든 값이 비어있는 행 제거 및 가장 최신 데이터만 선택
close_prices = data_wide['Close'].dropna(how='all')
latest_prices = close_prices.tail(1) # 가장 최근 거래일 데이터 선택

# 데이터 형태 변환
final_df = latest_prices.stack().reset_index()
final_df.columns = ['date', 'index_en', 'value']

# 한국어 지수 이름 매핑 및 전처리
ko_map = {key: val['ko'] for key, val in tickers_info.items()}
final_df['index_ko'] = final_df['index_en'].map(ko_map)
final_df.dropna(subset=['value'], inplace=True) # value가 없는 행 제거
final_df = final_df[['index_en', 'index_ko', 'date', 'value']]
final_df['date'] = final_df['date'].dt.strftime('%Y-%m-%dT%H:%M:%S')

# Supabase 클라이언트 설정 (환경 변수 사용)
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# 데이터 업로드
if not final_df.empty:
    data_to_upload = final_df.to_dict('records')
    try:
        data, count = supabase.table("financial_indices").insert(data_to_upload).execute()
        print(f"Successfully uploaded {len(data_to_upload)} records for date {final_df['date'].iloc[0]}.")
    except Exception as e:
        print(f"An error occurred during Supabase upload: {e}")
else:
    print("No data to upload after processing.")
