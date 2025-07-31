import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import os

#supabase 연결 정보
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# 미국 주식 목록
Name_US=['NVIDIA', 'Microsoft', 'Apple', 'Amazon', 'Alphabet (Google)', 'Meta Platforms (Facebook)', 'Broadcom', 'Berkshire Hathaway', 'Tesla', 'JPMorgan Chase', 'Walmart', 'Visa', 'Eli Lilly', 'Oracle', 'Netflix', 'Mastercard', 'Exxon Mobil', 'Costco', 'Procter & Gamble', 'Johnson & Johnson', 'Home Depot', 'Bank of America', 'AbbVie', 'Palantir', 'Coca-Cola', 'UnitedHealth', 'Philip Morris International', 'Cisco', 'T-Mobile US', 'Wells Fargo', 'IBM', 'General Electric', 'Salesforce', 'Chevron', 'Abbott Laboratories', 'Morgan Stanley', 'American Express', 'AMD', 'Walt Disney', 'Goldman Sachs', 'Intuit', 'ServiceNow', 'McDonald', 'AT&T', 'Merck', 'Texas Instruments', 'Uber', 'Intuitive Surgical', 'RTX', 'Blackstone Group', 'Caterpillar', 'Booking Holdings (Booking.com)', 'Pepsico', 'Verizon', 'QUALCOMM', 'BlackRock', 'Charles Schwab', 'Citigroup', 'Boeing', 'S&P Global', 'Thermo Fisher Scientific', 'Adobe', 'Amgen', 'Honeywell', 'Boston Scientific', 'Progressive', 'Applied Materials', 'Nextera Energy', 'Stryker Corporation', 'Danaher', 'Pfizer', 'Capital One', 'Union Pacific Corporation', 'GE Vernova', 'Deere & Company (John Deere)', 'TJX Companies', 'Gilead Sciences', 'Micron Technology', 'Palo Alto Networks', 'Comcast', 'Arista Networks', 'KKR & Co.', 'CrowdStrike', "Lowe's Companies", 'Lam Research', 'Automatic Data Processing', 'KLA', 'Analog Devices', 'Amphenol', 'ConocoPhillips', 'Vertex Pharmaceuticals', 'AppLovin', 'Strategy \n (MicroStrategy)', 'Nike', 'Lockheed Martin', 'Starbucks', 'Marsh & McLennan Companies', 'Intercontinental Exchange', 'American Tower', 'DoorDash']
Ticker_US=['NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOG', 'META', 'AVGO', 'BRK-B', 'TSLA', 'JPM', 'WMT', 'V', 'LLY', 'ORCL', 'NFLX', 'MA', 'XOM', 'COST', 'PG', 'JNJ', 'HD', 'BAC', 'ABBV', 'PLTR', 'KO', 'UNH', 'PM', 'CSCO', 'TMUS', 'WFC', 'IBM', 'GE', 'CRM', 'CVX', 'ABT', 'MS', 'AXP', 'AMD', 'DIS', 'GS', 'INTU', 'NOW', 'MCD', 'T', 'MRK', 'TXN', 'UBER', 'ISRG', 'RTX', 'BX', 'CAT', 'BKNG', 'PEP', 'VZ', 'QCOM', 'BLK', 'SCHW', 'C', 'BA', 'SPGI', 'TMO', 'ADBE', 'AMGN', 'HON', 'BSX', 'PGR', 'AMAT', 'NEE', 'SYK', 'DHR', 'PFE', 'COF', 'UNP', 'GEV', 'DE', 'TJX', 'GILD', 'MU', 'PANW', 'CMCSA', 'ANET', 'KKR', 'CRWD', 'LOW', 'LRCX', 'ADP', 'KLAC', 'ADI', 'APH', 'COP', 'VRTX', 'APP', 'MSTR', 'NKE', 'LMT', 'SBUX', 'MMC', 'ICE', 'AMT', 'DASH']


# 미국 동부 표준시 타임존 객체 생성 (New York 기준)
# 'America/New_York'는 서머타임을 자동으로 처리합니다.
eastern_time = pytz.timezone('America/New_York')
# 현재 시간을 미국 동부 표준시 기준으로 가져오기
today_eastern = datetime.now(eastern_time)
# yfinance의 end 날짜는 포함되지 않으므로, start를 오늘로, end를 내일로 설정하여 오늘 데이터 추출
start_date = today_eastern.strftime('%Y-%m-%d')
end_date = (today_eastern + timedelta(days=1)).strftime('%Y-%m-%d')



## 2. 미국 주식
us_history = []
for i in range(len(Name_US)):
    name = Name_US[i]
    Ticker = Ticker_US[i]
    ticker = yf.Ticker(Ticker)
    
    # 'period' 대신 'start'와 'end'를 사용하고, 하루치 데이터이므로 'interval="1d"' 사용
    hist = ticker.history(start=start_date, end=end_date)
    
    if not hist.empty:
        hist['name'] = name
        hist['Ticker'] = Ticker
        us_history.append(hist)

if us_history:
    #결과 데이터프레임 생성
    us_df = pd.DataFrame()
    us_df = pd.concat(us_history)

    #전처리
    us_df_formatted = us_df.reset_index()
    us_df_formatted = us_df_formatted[['Date', 'Ticker', 'name', 'Close', 'Volume']]
    us_df_formatted = us_df_formatted.rename(columns={
        'Date': 'time',
        'Ticker': 'ticker',
        'name': 'company_name',
        'Close': 'close_price',
        'Volume': 'volume'
    })
    ##결측치 제거
    us_df_formatted.dropna(inplace=True)
    
    #업로드용 데이터 변환
    data_to_upload_us = us_df_formatted.to_dict('records')
    #시간 형식 변경
    for record in data_to_upload_us:
        record['time'] = record['time'].isoformat()

    # 데이터 삽입 (upsert 사용)
    # 기본 키(time, ticker)가 겹치면 데이터를 덮어쓰고, 없으면 새로 추가합니다.
    try:
        data, count = supabase.table('us_stocks').upsert(data_to_upload_us).execute()
        print(f"✅ 성공적으로 업로드/업데이트되었습니다. 처리된 행 개수: {len(data[1])}")
    except Exception as e:
        print(f"🚨 업로드 중 오류가 발생했습니다: {e}")
else:
    print("ℹ️ 어제는 주식 시장이 열리지 않았거나, 가져올 데이터가 없습니다.")
