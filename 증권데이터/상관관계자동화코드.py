from supabase import create_client, Client
import pandas as pd
import os
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

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
korean_stocks['time'] = pd.to_datetime(korean_stocks['time'])
financial_indices['date'] = pd.to_datetime(financial_indices['date'])

# 2. 날짜만 추출
korean_stocks['date_only'] = korean_stocks['time'].dt.date
financial_indices['date_only'] = financial_indices['date'].dt.date

# 3. 결과 저장용 리스트
results = []

companies = korean_stocks['company_name'].unique()
indices = financial_indices['index_ko'].unique()

# 4. 기업별 루프
for company in companies:
    df_company_all = korean_stocks[korean_stocks['company_name'] == company]

    # 기업 ticker 추출 (하나만 있다고 가정)
    ticker = df_company_all['ticker'].iloc[0]

    df_company = df_company_all[['date_only', 'close_price']]

    for index in indices:
        df_index = financial_indices[financial_indices['index_ko'] == index]
        df_index = df_index[['date_only', 'value']]

        # 날짜 기준 inner join
        merged = pd.merge(df_company, df_index, on='date_only', how='inner')

        if len(merged) < 5:
            continue

        corr = merged['close_price'].corr(merged['value'])

        if pd.notna(corr):
            results.append({
                'company_name': company,
                'ticker': ticker,
                'index_ko': index,
                'correlation': corr
            })

# 6. 결과 데이터프레임 생성
corr_kor_index = pd.DataFrame(results)

# 결과를 다시 초기화하여 두 번째 상관관계 계산에 사용
results = []

# unique() 호출 전에 데이터프레임이 비어있을 경우를 대비하여 조건 추가
korean_companies = korean_stocks['company_name'].unique() if not korean_stocks.empty else []
us_companies = us_stocks['company_name'].unique() if not us_stocks.empty else []

for kor_company in korean_companies:
    df_kor_all = korean_stocks[korean_stocks['company_name'] == kor_company]

    # 한국 기업의 ticker 추출
    kor_ticker = df_kor_all['ticker'].iloc[0] if not df_kor_all.empty else None

    df_kor = df_kor_all[['date_only', 'close_price']]

    for us_company in us_companies:
        df_us_all = us_stocks[us_stocks['company_name'] == us_company]

        # 미국 기업의 ticker 추출
        us_ticker = df_us_all['ticker'].iloc[0] if not df_us_all.empty else None

        df_us = df_us_all[['date_only', 'close_price']]

        # 날짜 기준 병합
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

# 1. 첫 번째 데이터프레임: corr_kor_index (ticker 포함)
# 데이터프레임이 비어있지 않은 경우에만 삽입 시도
if not corr_kor_index.empty:
    for _, row in corr_kor_index.iterrows():
        data = {
            "company_name": row["company_name"],
            "ticker": row["ticker"],                 # ticker 컬럼 추가
            "index_ko": row["index_ko"],
            "correlation": None if pd.isna(row["correlation"]) else float(row["correlation"])
        }
        try:
            supabase.table("correlation_kor_index").insert(data).execute()
        except Exception as e:
            print(f"Error inserting into correlation_kor_index: {e}")

# 2. 두 번째 데이터프레임: corr_kor_us (korean_ticker, us_ticker 추가)
# 데이터프레임이 비어있지 않은 경우에만 삽입 시도
if not corr_kor_us.empty:
    for _, row in corr_kor_us.iterrows():
        data = {
            "korean_company": row["korean_company"],
            "korean_ticker": row["korean_ticker"],  # korean_ticker 추가
            "us_company": row["us_company"],
            "us_ticker": row["us_ticker"],          # us_ticker 추가
            "correlation": None if pd.isna(row["correlation"]) else float(row["correlation"])
        }
        try:
            supabase.table("correlation_kor_us").insert(data).execute()
        except Exception as e:
            print(f"Error inserting into correlation_kor_us: {e}")

print("Correlation calculation and insertion completed.")