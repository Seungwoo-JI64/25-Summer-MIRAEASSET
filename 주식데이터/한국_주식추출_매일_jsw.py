import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import os

# 1. API 호출 준비

#supabase 연결 정보
# .env 파일이 아니라 Github Actions에서 환경 변수를 설정하여 사용
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# 한국 주식 목록
Name_KR=['Samsung', 'SK Hynix', 'Samsung Biologics', 'LG Energy Solution', 'Hyundai', 'KB Financial Group', 'Celltrion', 'Doosan Enerbility', 'Kia', 'Hanwha Aerospace', 'Naver', 'HD Hyundai Heavy Industries', 'Shinhan Financial Group', 'Hyundai Mobis', 'Kakao', 'HMM', 'Hana Financial Group', 'POSCO', 'Korea Electric Power', 'Samsung Life Insurance', 'Hanwha Ocean (DSME)', 'HD Korea Shipbuilding & Offshore Engineering', 'SK Square', 'Meritz Financial Group', 'Alteogen', 'Hyundai Rotem Company', 'LG Chem', 'SK Innovation', 'Woori Financial Group', 'Krafton', 'HD Hyundai Electric', 'Industrial Bank of Korea (IBK)', 'Korea Zinc', 'Samsung SDI', 'KakaoBank', 'KT Corporation', 'KT&G (Korea Tobacco)', 'Samsung Heavy Industries', 'LG Electronics', 'LG Corp', 'SK Telecom', 'HYBE', 'SK Group', 'LIG Nex1', 'POSCO Chemical', 'Kakao Pay', 'Samsung Electro-Mechanics', 'Hyundai Glovis', 'Ecopro BM', 'Hanwha Systems', 'Samyang Foods', 'HANMI Semiconductor', 'Doosan', 'Korean Air Lines', 'Posco International', 'HD Hyundai Marine Solution', 'Korea Aerospace Industries', 'Amorepacific', 'Yuhan', 'S-OIL', 'Coway', 'Ecopro', 'Hanwha Solutions', 'Doosan Bobcat', 'Hankook Tire', 'Netmarble', 'LG Household & Health Care', 'LG Display', 'LS Corp.', 'ORION', 'Korea Gas', 'CJ Group', 'NCsoft', 'Kangwon Land', 'LEENO Industrial', 'F&F Co', 'SM Entertainment', 'Kumho Petrochemical', 'Hanmi Pharmaceutical', 'LOTTE Chemical', 'SHIFT UP', 'Pearl Abyss', 'JYP Entertainment', 'KCC Corp', 'Nongshim', 'Fila', 'BGF Retail', 'Pan Ocean', 'LOTTE Corporation', 'Asiana Airlines', 'Hansol Chemical', 'Shinsegae', 'YG Entertainment', 'Doosan Fuel Cell', 'Kakao Games', 'HiteJinro', 'Kumho Tire', 'Ottogi', 'SD BioSensor', 'DoubleUGames']
Ticker_KR=['005930.KS', '000660.KS', '207940.KS', '373220.KS', 'HYMTF', 'KB', '068270.KS', '034020.KS', '000270.KS', '012450.KS', '035420.KS', '329180.KS', 'SHG', '012330.KS', '035720.KS', '011200.KS', '086790.KS', 'PKX', 'KEP', '032830.KS', '042660.KS', '009540.KS', '402340.KS', '138040.KS', '196170.KQ', '064350.KS', '051910.KS', '096775.KS', 'WF', '259960.KS', '267260.KS', '024110.KS', '010130.KS', '006405.KS', '323410.KS', 'KT', '033780.KS', '010140.KS', '066570.KS', '003550.KS', 'SKM', '352820.KS', '034730.KS', '079550.KS', '003670.KS', '377300.KS', '009155.KS', '086280.KS', '247540.KQ', '272210.KS', '003230.KS', '042700.KS', '000150.KS', '003495.KS', '047050.KS', '443060.KS', '047810.KS', '090430.KS', '000100.KS', '010950.KS', '021240.KS', '086520.KQ', '009830.KS', '241560.KS', '161390.KS', '251270.KS', '051905.KS', 'LPL', '006260.KS', '271560.KS', '036460.KS', '001040.KS', '036570.KS', '035250.KS', '058470.KQ', '383220.KS', '041510.KQ', '011780.KS', '008930.KS', '011170.KS', '462870.KS', '263750.KQ', '035900.KQ', '002380.KS', '004370.KS', '081660.KS', '282330.KS', '028670.KS', '004990.KS', '020560.KS', '014680.KS', '004170.KS', '122870.KQ', '336260.KS', '293490.KQ', '000080.KS', '073240.KS', '007310.KS', '137310.KS', '192080.KS']

# 한국 주식을 불러오기 때문에 한국 시간 기준으로 진행
kst = pytz.timezone('Asia/Seoul') # 서울 타임존 객체 생성
today_kst = datetime.now(kst) # 현재 시간을 UTC+9 기준으로 가져오기
# start를 어제로, end를 오늘로 설정하여 오늘 데이터 추출
# 한국주식은 업데이트되기 시간이 걸리는 것으로 추정 -> 따라서 안전하게 전날의 데이터를 가져온다
start_date = (today_kst - timedelta(days=1)).strftime('%Y-%m-%d')
end_date = today_kst.strftime('%Y-%m-%d')

## 2. 한국 주식 불러오기
korea_history = [] # 저장
for i in range(len(Name_KR)): # 모든 한국 주식에 대하여 
    name = Name_KR[i]
    Ticker = Ticker_KR[i]
    ticker = yf.Ticker(Ticker) # 티커 기준으로 불러오기
    hist = ticker.history(start=start_date, end=end_date) # 하루의 데이터만 가져오기 # interval="1d"
    
    if not hist.empty:
        hist['name'] = name
        hist['Ticker'] = Ticker
        korea_history.append(hist)

if korea_history:
    # 결과 데이터프레임 생성
    korea_df = pd.DataFrame()
    korea_df = pd.concat(korea_history)

    # 전처리
    korea_df_formatted = korea_df.reset_index()
    korea_df_formatted = korea_df_formatted[['Date', 'Ticker', 'name', 'Close', 'Volume']]
    # 컬럼명 변경
    korea_df_formatted = korea_df_formatted.rename(columns={
        'Date': 'time',
        'Ticker': 'ticker',
        'name': 'company_name',
        'Close': 'close_price',
        'Volume': 'volume'
    })
    # 결측치 제거
    korea_df_formatted.dropna(inplace=True)

    #업로드용 데이터 변환
    data_to_upload_kr = korea_df_formatted.to_dict('records') # 각 행이 딕셔너리로, 전체 리스트로 변환
    #시간 형식 변경
    for record in data_to_upload_kr:
        record['time'] = record['time'].isoformat() # YYYY-MM-DDTHH:MM:SS 형식으로 변환
    #업로드
    try:
        data, count = supabase.table('korean_stocks').upsert(data_to_upload_kr).execute()
        print(f"성공적으로 업로드/업데이트되었습니다. 처리된 행 개수: {len(data[1])}")
    except Exception as e:
        print(f"업로드 중 오류가 발생했습니다: {e}")
else:
    print("어제는 주식 시장이 열리지 않았거나, 가져올 데이터가 없습니다.")
