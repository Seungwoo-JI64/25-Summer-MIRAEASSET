from supabase import create_client, Client
import pandas as pd
import os
import time
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import httpx # httpx.RemoteProtocolError를 임포트

url = "https://hcmniqyaqybzhmzmaumh.supabase.co"
key = os.environ.get("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)

def fetch_all_data(table_name, step=1000):
    all_data = []
    start = 0

    while True:
        response = supabase.table(table_name).select("*").range(start, start + step - 1).execute()
        data = response.data
        if not data:
            break
        all_data.extend(data)
        start += step
    return all_data

# 사용 예시
korean_stocks_data = fetch_all_data("korean_stocks")
financial_indices_data = fetch_all_data("financial_indices")
us_stocks_data = fetch_all_data("us_stocks")

korean_stocks = pd.DataFrame(korean_stocks_data)
financial_indices = pd.DataFrame(financial_indices_data)
us_stocks = pd.DataFrame(us_stocks_data)

# 1. datetime 변환
korean_stocks['time'] = pd.to_datetime(korean_stocks['time'], errors='coerce')
financial_indices['date'] = pd.to_datetime(financial_indices['date'], errors='coerce')
us_stocks['time'] = pd.to_datetime(us_stocks['time'], errors='coerce')

# 2. 날짜만 추출
korean_stocks['date_only'] = korean_stocks['time'].dt.date if 'time' in korean_stocks.columns and not korean_stocks['time'].isna().all() else pd.NaT
financial_indices['date_only'] = financial_indices['date'].dt.date if 'date' in financial_indices.columns and not financial_indices['date'].isna().all() else pd.NaT
us_stocks['date_only'] = us_stocks['time'].dt.date if 'time' in us_stocks.columns and not us_stocks['time'].isna().all() else pd.NaT

# 3. 결과 저장용 리스트
results = []

companies = korean_stocks['company_name'].unique() if not korean_stocks.empty else []
# financial_indices에서 'index_ko', 'index_ticker', 'index_en' 컬럼을 함께 가져오기 위해
# DataFrame으로 변환 후 unique 대신 필요한 컬럼만 추출
indices_info = financial_indices[['index_ko', 'index_ticker', 'index_en']].drop_duplicates().to_dict('records') \
                if not financial_indices.empty and 'index_ko' in financial_indices.columns and 'index_ticker' in financial_indices.columns and 'index_en' in financial_indices.columns \
                else []


# 4. 기업별 루프
for company in companies:
    df_company_all = korean_stocks[korean_stocks['company_name'] == company]
    if df_company_all.empty:
        continue

    ticker = df_company_all['ticker'].iloc[0] if 'ticker' in df_company_all.columns and not df_company_all.empty else None

    df_company = df_company_all[['date_only', 'close_price']]

    for index_info in indices_info: # 변경: index_info 딕셔너리로 반복
        index_ko = index_info['index_ko']
        index_ticker = index_info['index_ticker'] # 새로 추가
        index_en = index_info['index_en'] # 새로 추가

        df_index = financial_indices[financial_indices['index_ko'] == index_ko]
        if df_index.empty:
            continue
        df_index = df_index[['date_only', 'value']]

        merged = pd.merge(df_company, df_index, on='date_only', how='inner')

        if len(merged) < 5:
            continue

        corr = merged['close_price'].corr(merged['value'])

        if pd.notna(corr):
            results.append({
                'company_name': company,
                'ticker': ticker,
                'index_ko': index_ko,
                'index_ticker': index_ticker, # 새로 추가
                'index_en': index_en,         # 새로 추가
                'correlation': corr
            })

# 6. 결과 데이터프레임 생성
corr_kor_index = pd.DataFrame(results)


# 두 번째 상관관계 계산을 위한 변수 재정의
results = []

korean_unique_companies = korean_stocks['company_name'].unique() if not korean_stocks.empty else []
us_grouped = us_stocks.groupby('company_name') if not us_stocks.empty else {} # 빈 경우 {}로 처리하여 for-loop 오류 방지


for kor_company in korean_unique_companies:
    df_kor_all = korean_stocks[korean_stocks['company_name'] == kor_company]
    if df_kor_all.empty:
        continue
    kor_ticker = df_kor_all['ticker'].iloc[0] if 'ticker' in df_kor_all.columns and not df_kor_all.empty else None
    df_kor = df_kor_all[['date_only', 'close_price']]

    # us_grouped가 빈 딕셔너리인 경우 다음으로 넘어감
    if not us_grouped:
        continue

    for us_company, df_us_all in us_grouped:
        if df_us_all.empty:
            continue
        us_ticker = df_us_all['ticker'].iloc[0] if 'ticker' in df_us_all.columns and not df_us_all.empty else None
        df_us = df_us_all[['date_only', 'close_price']]
        merged = pd.merge(df_kor, df_us, on='date_only', how='inner', suffixes=('_kor', '_us'))
        if len(merged) < 5:
            continue
        corr = merged['close_price_kor'].corr(merged['close_price_us'])
        if pd.notna(corr):
            results.append({
                'korean_company': kor_company,
                'korean_ticker': kor_ticker,
                'us_company': us_company,
                'us_ticker': us_ticker,
                'correlation': corr
            })


# 결과 저장
corr_kor_us = pd.DataFrame(results)

# 재시도 데코레이터 정의 (필요하다면 tenacity 라이브러리 설치 필요)
@retry(stop=stop_after_attempt(5), wait=wait_fixed(2), retry=retry_if_exception_type(httpx.RemoteProtocolError))
def upsert_to_supabase(table_name, data, on_conflict_cols):
    print(f"Attempting to upsert {len(data)} rows into {table_name} with conflict on {on_conflict_cols}...")
    supabase.table(table_name).upsert(data, on_conflict=on_conflict_cols).execute()
    print(f"Successfully upserted data into {table_name}.")


# === Upsert 적용 및 index_ticker, index_en 추가 부분 ===

# 1. 한국 기업 - 지수 상관관계 저장
if not corr_kor_index.empty:
    data_to_insert_kor_index = corr_kor_index.where(pd.notna(corr_kor_index), None).to_dict('records')
    try:
        # on_conflict 파라미터에 'index_ticker' 추가
        upsert_to_supabase(
            "correlation_kor_index",
            data_to_insert_kor_index,
            "company_name,ticker,index_ko,index_ticker" # <-- index_ticker 추가
        )
    except Exception as e:
        print(f"Failed to upsert into correlation_kor_index after multiple retries: {e}")

# 2. 한국 - 미국 기업 상관관계 저장 (이 부분은 변경 없음)
if not corr_kor_us.empty:
    data_to_insert_kor_us = corr_kor_us.where(pd.notna(corr_kor_us), None).to_dict('records')
    try:
        upsert_to_supabase(
            "correlation_kor_us",
            data_to_insert_kor_us,
            "korean_company,korean_ticker,us_company,us_ticker"
        )
    except Exception as e:
        print(f"Failed to upsert into correlation_kor_us after multiple retries: {e}")

print("Correlation calculation and insertion completed.")