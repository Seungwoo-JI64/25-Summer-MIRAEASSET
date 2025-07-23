#################################
# 1. 연관 뉴스 분석 에이전트

# RAG를 통해 기업 설명과 관련된 뉴스 15개를 1차 추출
# 이후 Gemini AI를 사용하여 가장 영향력 있는 뉴스 3개를 선택한다
# 이 결과는 state의 DomesticNews 클래스에 저장된다.

import os
import json
import time
from typing import Dict, Any, List

# --- 추가된 라이브러리 ---
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import ast
# -------------------------

from google import genai
from google.genai import types

# 상위 폴더에 있는 state.py 모듈에서 AnalysisState 클래스를 가져옵니다.
from ..state import AnalysisState, DomesticNews

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# --- Gemini API 설정 ---
# 루트폴더의 .env 파일에 저장한 Gemini 접속 정보를 불러온다.
API_KEY = os.environ.get("GEMINI_API_KEY_2")
if not API_KEY:
    raise EnvironmentError("GEMINI_API_KEY를 환경 변수로 설정해야 합니다.")
# Gemini 클라이언트를 설정합니다.
client = genai.Client(api_key=API_KEY)



# Supabase 접속 정보를 환경 변수에서 가져옵니다.
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# 접속 정보가 없으면 에러를 발생시킵니다.
if not all([url, key]):
    raise EnvironmentError("SUPABASE_URL 및 SUPABASE_KEY를 환경 변수로 설정해야 합니다.")

# Supabase 클라이언트를 생성합니다.
supabase: Client = create_client(url, key)

# 프로그램 시작 시 한 번만 데이터를 로드하고 전처리하여 효율성을 높입니다.
print("Supabase에서 기업 및 뉴스 데이터 로딩 및 전처리를 시작합니다...")
df_company = pd.DataFrame(supabase.table("company_summary").select("company_name,ticker, summary, summary_embedding").execute().data)
df_news = pd.DataFrame(supabase.table("ko_financial_news_summary").select("title, url, summary, embedding, publish_date").execute().data)
df_news['publish_date'] = pd.to_datetime(df_news['publish_date']).dt.strftime('%Y-%m-%d')

# 임베딩 컬럼(문자열)을 실제 벡터(Numpy 배열)로 변환합니다.
df_company['embedding_array'] = df_company['summary_embedding'].apply(lambda x: np.array(ast.literal_eval(x)))
df_news['embedding_array'] = df_news['embedding'].apply(lambda x: np.array(ast.literal_eval(x)))
print("데이터 로딩 및 전처리 완료.")
# ---------------------------------------------

# --- 사전 정의된 엔티티 및 지표 매핑 ---
# 기계가 사용하는 Ticker(Key)와 사람이 이해하는 이름(Value)을 명확히 분리합니다.
# 이 구조를 통해 AI는 사람이 이해하는 이름으로 작업하고,
# 시스템은 Ticker를 사용하여 다음 단계의 분석을 수행합니다.

METRICS_MAP = {
    # === 지수 ===
    '^GSPC': {'name': 'S&P 500 지수', "type": "index"},
    '^KS11': {'name': '코스피 지수', "type": "index"},
    'CL=F': {'name': 'WTI 원유 선물', "type": "index"},
    'USDKRW=X': {'name': '달러/원 환율', "type": "index"},
    # === 미국 기업 ===
    "NVDA": {
        "name": "NVIDIA",
        "type": "stock"
    },
    "MSFT": {
        "name": "Microsoft",
        "type": "stock"
    },
    "AAPL": {
        "name": "Apple",
        "type": "stock"
    },
    "AMZN": {
        "name": "Amazon",
        "type": "stock"
    },
    "GOOG": {
        "name": "Alphabet (Google)",
        "type": "stock"
    },
    "META": {
        "name": "Meta Platforms (Facebook)",
        "type": "stock"
    },
    "AVGO": {
        "name": "Broadcom",
        "type": "stock"
    },
    "BRK-B": {
        "name": "Berkshire Hathaway",
        "type": "stock"
    },
    "TSLA": {
        "name": "Tesla",
        "type": "stock"
    },
    "JPM": {
        "name": "JPMorgan Chase",
        "type": "stock"
    },
    "WMT": {
        "name": "Walmart",
        "type": "stock"
    },
    "V": {
        "name": "Visa",
        "type": "stock"
    },
    "LLY": {
        "name": "Eli Lilly",
        "type": "stock"
    },
    "ORCL": {
        "name": "Oracle",
        "type": "stock"
    },
    "NFLX": {
        "name": "Netflix",
        "type": "stock"
    },
    "MA": {
        "name": "Mastercard",
        "type": "stock"
    },
    "XOM": {
        "name": "Exxon Mobil",
        "type": "stock"
    },
    "COST": {
        "name": "Costco",
        "type": "stock"
    },
    "PG": {
        "name": "Procter & Gamble",
        "type": "stock"
    },
    "JNJ": {
        "name": "Johnson & Johnson",
        "type": "stock"
    },
    "HD": {
        "name": "Home Depot",
        "type": "stock"
    },
    "BAC": {
        "name": "Bank of America",
        "type": "stock"
    },
    "ABBV": {
        "name": "AbbVie",
        "type": "stock"
    },
    "PLTR": {
        "name": "Palantir",
        "type": "stock"
    },
    "KO": {
        "name": "Coca-Cola",
        "type": "stock"
    },
    "UNH": {
        "name": "UnitedHealth",
        "type": "stock"
    },
    "PM": {
        "name": "Philip Morris International",
        "type": "stock"
    },
    "CSCO": {
        "name": "Cisco",
        "type": "stock"
    },
    "TMUS": {
        "name": "T-Mobile US",
        "type": "stock"
    },
    "WFC": {
        "name": "Wells Fargo",
        "type": "stock"
    },
    "IBM": {
        "name": "IBM",
        "type": "stock"
    },
    "GE": {
        "name": "General Electric",
        "type": "stock"
    },
    "CRM": {
        "name": "Salesforce",
        "type": "stock"
    },
    "CVX": {
        "name": "Chevron",
        "type": "stock"
    },
    "ABT": {
        "name": "Abbott Laboratories",
        "type": "stock"
    },
    "MS": {
        "name": "Morgan Stanley",
        "type": "stock"
    },
    "AXP": {
        "name": "American Express",
        "type": "stock"
    },
    "AMD": {
        "name": "AMD",
        "type": "stock"
    },
    "DIS": {
        "name": "Walt Disney",
        "type": "stock"
    },
    "INTU": {
        "name": "Intuit",
        "type": "stock"
    },
    "NOW": {
        "name": "ServiceNow",
        "type": "stock"
    },
    "MCD": {
        "name": "McDonald",
        "type": "stock"
    },
    "T": {
        "name": "AT&T",
        "type": "stock"
    },
    "MRK": {
        "name": "Merck",
        "type": "stock"
    },
    "TXN": {
        "name": "Texas Instruments",
        "type": "stock"
    },
    "UBER": {
        "name": "Uber",
        "type": "stock"
    },
    "ISRG": {
        "name": "Intuitive Surgical",
        "type": "stock"
    },
    "RTX": {
        "name": "RTX",
        "type": "stock"
    },
    "BX": {
        "name": "Blackstone Group",
        "type": "stock"
    },
    "CAT": {
        "name": "Caterpillar",
        "type": "stock"
    },
    "BKNG": {
        "name": "Booking Holdings (Booking.com)",
        "type": "stock"
    },
    "PEP": {
        "name": "Pepsico",
        "type": "stock"
    },
    "VZ": {
        "name": "Verizon",
        "type": "stock"
    },
    "QCOM": {
        "name": "QUALCOMM",
        "type": "stock"
    },
    "BLK": {
        "name": "BlackRock",
        "type": "stock"
    },
    "SCHW": {
        "name": "Charles Schwab",
        "type": "stock"
    },
    "C": {
        "name": "Citigroup",
        "type": "stock"
    },
    "BA": {
        "name": "Boeing",
        "type": "stock"
    },
    "SPGI": {
        "name": "S&P Global",
        "type": "stock"
    },
    "TMO": {
        "name": "Thermo Fisher Scientific",
        "type": "stock"
    },
    "ADBE": {
        "name": "Adobe",
        "type": "stock"
    },
    "AMGN": {
        "name": "Amgen",
        "type": "stock"
    },
    "HON": {
        "name": "Honeywell",
        "type": "stock"
    },
    "BSX": {
        "name": "Boston Scientific",
        "type": "stock"
    },
    "PGR": {
        "name": "Progressive",
        "type": "stock"
    },
    "AMAT": {
        "name": "Applied Materials",
        "type": "stock"
    },
    "NEE": {
        "name": "Nextera Energy",
        "type": "stock"
    },
    "SYK": {
        "name": "Stryker Corporation",
        "type": "stock"
    },
    "DHR": {
        "name": "Danaher",
        "type": "stock"
    },
    "PFE": {
        "name": "Pfizer",
        "type": "stock"
    },
    "COF": {
        "name": "Capital One",
        "type": "stock"
    },
    "UNP": {
        "name": "Union Pacific Corporation",
        "type": "stock"
    },
    "GEV": {
        "name": "GE Vernova",
        "type": "stock"
    },
    "DE": {
        "name": "Deere & Company (John Deere)",
        "type": "stock"
    },
    "TJX": {
        "name": "TJX Companies",
        "type": "stock"
    },
    "GILD": {
        "name": "Gilead Sciences",
        "type": "stock"
    },
    "MU": {
        "name": "Micron Technology",
        "type": "stock"
    },
    "PANW": {
        "name": "Palo Alto Networks",
        "type": "stock"
    },
    "CMCSA": {
        "name": "Comcast",
        "type": "stock"
    },
    "ANET": {
        "name": "Arista Networks",
        "type": "stock"
    },
    "KKR": {
        "name": "KKR & Co.",
        "type": "stock"
    },
    "CRWD": {
        "name": "CrowdStrike",
        "type": "stock"
    },
    "LOW": {
        "name": "Lowe's Companies",
        "type": "stock"
    },
    "LRCX": {
        "name": "Lam Research",
        "type": "stock"
    },
    "ADP": {
        "name": "Automatic Data Processing",
        "type": "stock"
    },
    "KLAC": {
        "name": "KLA",
        "type": "stock"
    },
    "ADI": {
        "name": "Analog Devices",
        "type": "stock"
    },
    "APH": {
        "name": "Amphenol",
        "type": "stock"
    },
    "COP": {
        "name": "ConocoPhillips",
        "type": "stock"
    },
    "VRTX": {
        "name": "Vertex Pharmaceuticals",
        "type": "stock"
    },
    "APP": {
        "name": "AppLovin",
        "type": "stock"
    },
    "MSTR": {
        "name": "Strategy  (MicroStrategy)",
        "type": "stock"
    },
    "NKE": {
        "name": "Nike",
        "type": "stock"
    },
    "LMT": {
        "name": "Lockheed Martin",
        "type": "stock"
    },
    "SBUX": {
        "name": "Starbucks",
        "type": "stock"
    },
    "MMC": {
        "name": "Marsh & McLennan Companies",
        "type": "stock"
    },
    "ICE": {
        "name": "Intercontinental Exchange",
        "type": "stock"
    },
    "AMT": {
        "name": "American Tower",
        "type": "stock"
    },
    "DASH": {
        "name": "DoorDash",
        "type": "stock"
    }
}




# --- RAG 함수 ---
# 15개의 뉴스 후보를 검색하는 가상 RAG 함수입니다.
############ 미리 생성한 것을 사용합니다.
def search_relevant_news_rag(company_name: str) -> List[Dict[str, str]]:
    """
    Supabase에 저장된 벡터를 사용하여, 특정 기업 설명과 가장 유사한 뉴스 15개를 검색합니다.
    이때 검색 대상 기업의 티커를 모든 뉴스 결과에 포함하여 반환합니다.
    """
    print(f"🔍 [News Analyst] Supabase 벡터 검색으로 '{company_name}' 관련 뉴스 15개를 검색합니다.")

    try:
        # 1. 전역 df_company 데이터프레임에서 분석할 기업의 행을 찾습니다.
        company_row = df_company[df_company['company_name'] == company_name]
        if company_row.empty:
            print(f"경고: DB에서 '{company_name}' 기업 정보를 찾을 수 없습니다.")
            return []

        # --- [수정된 부분 1: 티커 정보 조회] ---
        # 2. 해당 기업의 임베딩 벡터와 '티커'를 가져옵니다.
        company_vec = company_row.iloc[0]['embedding_array'].reshape(1, -1)
        company_ticker = company_row.iloc[0]['ticker'] # 검색 대상 기업의 티커를 변수에 저장
        # --- [수정 끝] ---


        # 3. 전체 뉴스의 임베딩 벡터들과 코사인 유사도를 한 번에 계산합니다.
        news_embeddings = np.vstack(df_news['embedding_array'].values)
        similarities = cosine_similarity(company_vec, news_embeddings)[0]

        # 4. 계산된 유사도 점수가 가장 높은 상위 15개 뉴스의 인덱스를 찾습니다.
        top_indices = similarities.argsort()[-15:][::-1]

        # 5. 해당 인덱스의 뉴스 정보(제목, 요약, URL 등)를 추출합니다.
        top_news_df = df_news.iloc[top_indices][['title', 'summary', 'url', 'publish_date']]

        # --- [수정된 부분 2: 조회한 티커 추가] ---
        # 6. 검색된 모든 뉴스(DataFrame)에 검색 대상 기업의 티커를 새로운 컬럼으로 추가합니다.
        top_news_df['ticker'] = company_ticker
        # --- [수정 끝] ---

        # 7. 결과를 AI가 처리하기 쉬운 List[Dict] 형태로 변환하여 반환합니다.
        #    컬럼 순서를 조정하여 ticker가 앞에 오게 합니다.
        return top_news_df[['ticker', 'title', 'summary', 'url', 'publish_date']].to_dict('records')

    except Exception as e:
        print(f"RAG 뉴스 검색 중 오류가 발생했습니다: {e}")
        return []




# --- GEMINI 뉴스 선정 함수 ---
# RAG의 결과 중 최종 3개 정도를 gemini로 선별한다
# 뉴스 제목이 아니라 뉴스 목록의 인덱스를 반환하도록 한다.
# 프롬프트에는 기업명 뿐만이 아니라 기업의 설명, 여러 지표 목록과 이에 대응되는 ticker들을 넣어야 한다.
def select_top_news_with_gemini(
    company_name: str,
    company_description: str,
    news_list: List[Dict[str, str]],
    # us_entities_for_prompt는 이제 "이름 (티커)" 형식의 리스트를 받습니다.
    us_entities_for_prompt: List[str]
) -> List[Dict[str, Any]]:
    """
    Gemini AI를 사용하여 뉴스 3개를 선별하고, 관련된 미국 기업/지표의 티커를 추출합니다.
    """
    print("[News Analyst] Gemini AI를 호출하여 15개 뉴스 중 핵심 뉴스 3개를 선별합니다.")

    # "이름 (티커)" 형식의 리스트를 프롬프트에 넣기 좋게 문자열로 변환합니다.
    entities_prompt_list = ", ".join(f'"{item}"' for item in us_entities_for_prompt)

    # --- [수정] 프롬프트를 좀 더 강하고 명확하게 수정하여 AI가 다른 텍스트를 생성하지 않도록 유도 ---
    prompt_parts = [
        f"You are a silent JSON-generating robot. Your sole purpose is to return a valid JSON object based on the instructions.",
        f"Analyze news about the target company ({company_name}) and connect it to a predefined list of US entities.",
        "\n### TARGET COMPANY INFORMATION ###",
        f"Company Name: {company_name}",
        f"Company Description: {company_description}",
        "\n### INSTRUCTIONS ###",
        "1. From the 'TARGET COMPANY NEWS LIST' below, select the 3 most impactful news articles.",
        "2. For EACH of the 3 selected news, identify 1-2 MOST relevant tickers from the 'US ENTITY LIST'. The ticker is inside the parentheses `()`. ",
        "3. **You MUST return your answer ONLY as a single, valid JSON object.**",
        "4. **DO NOT include any other text, explanation, or markdown like ```json. Your entire response must be ONLY the JSON object itself, starting with `{` and ending with `}`.**",
        "5. Can you extract as many Korea-related tickers as possible, like the USD/KRW exchange rate ('USDKRW=X') or the KOSPI index ('^KS11')?"
        "\n### US ENTITY LIST (Name (Ticker)) ###",
        # 이제 "NVIDIA (NVDA)" 와 같은 명확한 정보가 AI에게 제공됩니다.
        f"[{entities_prompt_list}]",
        "\n### OUTPUT FORMAT EXAMPLE ###",
        # 예시를 통해 AI가 반환해야 할 형식을 다시 한번 명확히 보여줍니다.
        "{\"selected_domestic_news\": [{\"index\": 1, \"related_tickers\": [\"NVDA\"]}, {\"index\": 2, \"related_tickers\": [\"^NDX\", \"USDKRW=X\"]}, {\"index\": 8, \"related_tickers\": [\"MSFT\"]}]}",
        "\n--- TARGET COMPANY NEWS LIST ---\n"
    ]
    # --- [프롬프트 수정 끝] ---

    # 15개의 뉴스 항목을 프롬프트에 추가합니다.
    for i, news in enumerate(news_list):
        # 이제 news 딕셔너리에 ticker가 있지만, AI의 혼동을 막기 위해 프롬프트에는 넣지 않는 것이 좋습니다.
        # AI는 오직 US ENTITY LIST에서만 티커를 선택해야 합니다.
        prompt_parts.append(f"[{i}] Title: {news['title']}\nSummary: {news['summary']}\n")
    prompt = "\n".join(prompt_parts)

    try:
        # API 키를 환경 변수에서 가져옵니다.
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

        client = genai.Client(api_key=api_key)
        model = "gemini-2.5-flash"
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])] 
        
        # 이전 예시 코드의 generate_content_config 형식을 따릅니다.
        generate_content_config = types.GenerateContentConfig(
            thinking_config = types.ThinkingConfig(
                thinking_budget=-1,
            ),
            tools=[
                types.Tool(googleSearch=types.GoogleSearch()), # 예시 코드에 포함된 도구
            ],
            response_mime_type="text/plain", # JSON을 텍스트로 받으므로 plain text
        )

        # generate_content_stream 호출로 변경하고 stream=True 인자를 제거합니다.
        response_stream = client.models.generate_content_stream( 
            model=model, 
            contents=contents, 
            config=generate_content_config,
        )

        response_text = ""
        for chunk in response_stream:
            response_text += chunk.text
            
        # --- [추가] AI의 원본 응답을 확인하기 위한 디버깅 코드 ---
        print("\n" + "="*40)
        print(">>> Gemini API Raw Response (for Debugging) <<<")
        print(response_text)
        print("="*40 + "\n")
        # --- [디버깅 코드 추가 끝] ---

        # --- [수정] JSON 파싱 로직을 더 안정적으로 변경하고, 실패 시 상세 에러를 출력 ---
        try:
            # 모델이 응답 앞뒤에 ```json ... ``` 같은 마크다운을 붙이는 경우가 많습니다.
            if '```json' in response_text:
                # 마크다운 블록이 있다면 그 안의 내용만 추출합니다.
                # rfind를 사용하여 마지막 ```json을 찾고, 그 이후 첫 ```을 찾습니다.
                start_marker = '```json'
                end_marker = '```'
                start_index = response_text.rfind(start_marker)
                
                if start_index != -1:
                    json_candidate = response_text[start_index + len(start_marker):]
                    end_index = json_candidate.find(end_marker)
                    if end_index != -1:
                        json_string = json_candidate[:end_index].strip()
                    else: # 닫는 마크다운이 없는 경우, 끝까지 사용
                        json_string = json_candidate.strip()
                else: # ```json 마커가 없는 경우
                    json_string = response_text.strip()
            else: # 마크다운이 없는 경우, 기존 로직 사용
                start_index = response_text.find('{')
                end_index = response_text.rfind('}') + 1
                if start_index != -1 and end_index > start_index:
                    json_string = response_text[start_index:end_index]
                else:
                    # 응답에서 JSON 객체의 시작과 끝을 찾을 수 없는 경우
                    raise ValueError("Could not find a valid JSON object structure in the response.")

            result = json.loads(json_string)
            
            # 응답 구조가 예상과 맞는지 한 번 더 확인합니다.
            if 'selected_domestic_news' not in result or not isinstance(result['selected_domestic_news'], list):
                 raise ValueError("JSON is valid, but the 'selected_domestic_news' key is missing or not a list.")

            print(f"Gemini가 성공적으로 파싱한 뉴스 정보: {result['selected_domestic_news']}")
            return result['selected_domestic_news']

        except (json.JSONDecodeError, IndexError, ValueError) as e:
            # JSON 파싱 과정에서 어떤 종류의 에러가 발생했는지 명확히 출력합니다.
            print(f"!!! [ERROR] Failed to parse JSON from Gemini's response. Reason: {e}")
            # 여기서 에러를 다시 발생시켜 바깥쪽 except 블록이 비상 모드를 실행하도록 합니다.
            raise
        # --- [파싱 로직 수정 끝] ---

    except Exception as e:
        print(f"Gemini API 호출 또는 응답 처리 중 에러 발생: {e}")
        fallback_result = [{"index": i, "related_tickers": []} for i in range(min(3, len(news_list)))]
        print(f"비상 모드: 가장 관련성 높은 뉴스 {len(fallback_result)}개를 임시로 선택합니다.")
        return fallback_result


def run_domestic_news_analyst(state: AnalysisState) -> Dict[str, Any]:
    """
    뉴스 분석 에이전트의 실행 함수.
    RAG로 뉴스를 검색하고 Gemini로 핵심 뉴스를 선별하여 상태를 업데이트합니다.
    """
    print("\n---  뉴스 분석 에이전트 실행 ---")
    company_name = state["company_name"] #기업 이름 가져오기
    company_description = state["company_description"] #기업 설명 가져오기

    # 1. RAG를 통해 관련 뉴스 15개 검색
    candidate_news = search_relevant_news_rag(company_name)
    if not candidate_news:
        return {"selected_domestic_news": []} # 검색된 뉴스 없으면 빈 리스트 반환

    # 2. Gemini 프롬프트에 사용할 미국 기업/지표 목록을 "이름 (티커)" 형식으로 생성합니다.
    #    AI가 이름과 티커를 명확하게 매칭할 수 있도록 정보를 함께 제공합니다.
    #    예: ["NVIDIA (NVDA)", "S&P 500 지수 (^GSPC)", ...]
    us_entities_for_prompt = [f"{v['name']} ({k})" for k, v in METRICS_MAP.items()]
    # reverse_metrics_map은 더 이상 필요하지 않으므로 삭제하거나 주석 처리할 수 있습니다.
    
     # 3. Gemini를 통해 뉴스 3개 선별 및 관련 미국 기업/지표 Ticker 추출
    selected_domestic_news_data = select_top_news_with_gemini(
        company_name, company_description, candidate_news, us_entities_for_prompt
    )
    if not selected_domestic_news_data:
        print("[News Analyst] Gemini로부터 유효한 뉴스 선택 결과를 받지 못했습니다.")
        return {"selected_domestic_news": []}
    
    # 4. Gemini 결과를 기반으로 최종 뉴스 목록 구성
    final_news_list: List[DomesticNews] = []
    for news_info in selected_domestic_news_data:
        # Gemini가 알려준 인덱스와 Ticker 목록을 가져옵니다.
        index = news_info.get("index")
        related_tickers = news_info.get("related_tickers", [])

        # Gemini가 잘못된 인덱스를 주었을 경우를 대비한 안전장치
        if index is None or not (0 <= index < len(candidate_news)):
            continue
        
        # 인덱스를 사용해 RAG가 찾았던 원본 뉴스 정보를 가져옵니다.
        news_item = candidate_news[index]
        
        # Ticker 목록에 해당하는 '이름' 목록을 찾습니다.
        # state.py의 DomesticNews 클래스는 'entities' 필드에 이름 목록을 요구합니다.
        entity_names = [v['name'] for k, v in METRICS_MAP.items() if k in related_tickers]

        # 최종 형식인 DomesticNews 객체를 생성합니다.
        selected_domestic_news_item: DomesticNews = {
            "title": news_item["title"],
            "url": news_item["url"],
            "summary": news_item["summary"],
            "publish_date": news_item["publish_date"],
            "entities": entity_names,
            "related_metrics": related_tickers,
        }
        final_news_list.append(selected_domestic_news_item)
        print(f"  - 뉴스 선별: \"{news_item['title']}\" (연관 Ticker: {related_tickers})")

    return {"selected_domestic_news": final_news_list}
