#################################
# 1. 연관 뉴스 분석 에이전트

# RAG를 통해 기업 설명과 관련된 뉴스 15개를 1차 추출
# 이후 Gemini AI를 사용하여 가장 영향력 있는 뉴스 3개를 선택한다
# 이 결과는 state의 SelectedNews 클래스에 저장된다.

import os
import json
import time
from typing import Dict, Any, List
from google import genai
from google.genai import types


# 상위 폴더에 있는 state.py 모듈에서 AnalysisState 클래스를 가져옵니다.
from ..state import AnalysisState, SelectedNews

# --- Gemini API 설정 ---
# 루트폴더의 .env 파일에 저장한 Gemini 접속 정보를 불러온다.
API_KEY = os.environ.get("GEMINI_API_KEY_2")
if not API_KEY:
    raise EnvironmentError("GEMINI_API_KEY를 환경 변수로 설정해야 합니다.")
# Gemini 클라이언트를 설정합니다.
client = genai.Client(api_key=API_KEY)


# --- 사전 정의된 엔티티 및 지표 매핑 ---
# 기계가 사용하는 Ticker(Key)와 사람이 이해하는 이름(Value)을 명확히 분리합니다.
# 이 구조를 통해 AI는 사람이 이해하는 이름으로 작업하고,
# 시스템은 Ticker를 사용하여 다음 단계의 분석을 수행합니다.

METRICS_MAP = {
    # === 지수 ===
    '^GSPC': {'name': 'S&P 500 지수', "type": "index"},
    '^NDX': {'name': '나스닥 100 지수', "type": "index"},
    '^DJI': {'name': '다우존스 산업평균지수', "type": "index"},
    '^KS11': {'name': '코스피 지수', "type": "index"},
    '^KQ11': {'name': '코스닥 지수', "type": "index"},
    'LIT': {'name': '리튬 ETF', "type": "index"},
    '^TNX': {'name': '미국 10년물 국채 수익률', "type": "index"},
    'NBI': {'name': '나스닥 바이오테크놀로지 지수', "type": "index"},
    '^VIX': {'name': 'CBOE 변동성 지수', "type": "index"},
    'CL=F': {'name': 'WTI 원유 선물', "type": "index"},
    'FDN': {'name': '다우존스 인터넷 지수', "type": "index"},
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
    "GS": {
        "name": "Goldman Sachs",
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
    """가상 RAG 함수. 회사 이름에 따라 15개의 뉴스 후보를 반환합니다."""
    print(f"🔍 [News Analyst] RAG 시스템으로 '{company_name}' 관련 뉴스 15개를 검색합니다.")
    return 




# --- GEMINI 뉴스 선정 함수 ---
# RAG의 결과 중 최종 3개 정도를 gemini로 선별한다
# 뉴스 제목이 아니라 뉴스 목록의 인덱스를 반환하도록 한다.
# 프롬프트에는 기업명 뿐만이 아니라 기업의 설명, 여러 지표 목록과 이에 대응되는 ticker들을 넣어야 한다.
def select_top_news_with_gemini(
    company_name: str, # 내가 보고자 하는 기업 이름
    company_description: str, #내가 보고자 하는 기업의 설명
    news_list: List[Dict[str, str]], # RAG로 검색된 뉴스 목록
    us_entities_for_prompt: List[str] # METRICS_MAP - 미국 기업/지표 목록 (티커 형태로)
) -> List[Dict[str, Any]]:
    """
    Gemini AI를 사용하여 분석 대상 기업의 뉴스 3개를 선별하고,
    각 뉴스와 관련된 미국 기업/지표의 티커를 1~2개 추출하는 함수.

    출력:
        List[int]: 선택된 뉴스 3개의 인덱스 목록.
    """
    print("[News Analyst] Gemini AI를 호출하여 15개 뉴스 중 핵심 뉴스 3개를 선별합니다.")

    entities_prompt_list = ", ".join(f'"{name}"' for name in us_entities_for_prompt) # METRICS_MAP에서 name만 추출한다.

    # Gemini에 전달할 프롬프트를 구성합니다.
    # 뉴스 목록 전체를 전달하고, 가장 영향력 있는 3개를 골라달라고 요청합니다.
    prompt_parts = [
        f"You are an expert analyst. Your task is to find connections between news about a specific target company ({company_name}) and a predefined list of US companies and indices.",
        "\n### TARGET COMPANY INFORMATION ###",
        f"Company Name: {company_name}",
        f"Company Description: {company_description}",
        "\n### INSTRUCTIONS ###",
        "1. From the 'TARGET COMPANY NEWS LIST' below, select the 3 most important news articles.",
        "2. For EACH of the 3 selected news, identify the 1 or 2 MOST relevant US companies or indices from the 'US ENTITY LIST'.",
        "3. Return your answer ONLY as a single JSON object. The object must contain a key 'selected_news', which is a list of objects. Each object must have two keys: 'index' (integer) and 'related_tickers' (a list of 1-2 ticker strings from the US entity list).",
        "\n### US ENTITY LIST (Find connections to these) ###",
        f"[{entities_prompt_list}]",
        "\n### EXAMPLE OUTPUT FORMAT ###",
        "{\"selected_news\": [{\"index\": 1, \"related_tickers\": [\"NVDA\"]}, {\"index\": 2, \"related_tickers\": [\"^NDX\", \"USDKRW=X\"]}]}",
        "\n--- TARGET COMPANY NEWS LIST ---\n"
    ]

    # 15개의 뉴스 항목을 프롬프트에 추가합니다.
    for i, news in enumerate(news_list):
        prompt_parts.append(f"[{i}] Title: {news['title']}\nSummary: {news['summary']}\n")
    prompt = "\n".join(prompt_parts)

    # API 작동
    try:
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt) #프롬프트 입력
                ]
            )
        ]

        # Gemini API를 호출하여 응답을 받습니다.
        model = "gemini-2.5-flash"
        response=client.models.generate_content_stream(model=model, contents=contents)

        # 모델의 응답(JSON)을 파싱합니다.
        # 응답 텍스트에서 첫 '{'와 마지막 '}'를 찾아 그 사이의 문자열을 파싱합니다.
        response_text = response.text
        start_index = response_text.find('{')
        end_index = response_text.rfind('}') + 1
        if start_index != -1 and end_index != 0:
            json_string = response_text[start_index:end_index]
            result = json.loads(json_string)
        else:
            # JSON을 찾지 못한 경우 예외 처리
            raise ValueError("응답에서 유효한 JSON 객체를 찾을 수 없습니다.")

        
        print(f"Gemini가 선택한 뉴스 인덱스: {result['selected_indices']}")
        return result['selected_indices']
    except Exception as e:
        print(f"Gemini API 호출 또는 JSON 파싱 중 에러 발생: {e}")
        # 에러 발생 시, 가장 관련성 높아보이는 앞의 3개를 임시로 선택합니다.
        return [0, 1, 2]


def run_news_analyst(state: AnalysisState) -> Dict[str, Any]:
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
        return {"selected_news": []} # 검색된 뉴스 없으면 빈 리스트 반환
    
    # 2. Gemini 프롬프트에 사용할 미국 기업/지표 이름 목록과, Ticker를 찾기 위한 역방향 맵 생성
    us_entities_for_prompt = [v["name"] for v in METRICS_MAP.values()]
    reverse_metrics_map = {v["name"]: k for k, v in METRICS_MAP.items()}
    
    # 3. Gemini를 통해 뉴스 3개 선별 및 관련 미국 기업/지표 Ticker 추출
    selected_news_data = select_top_news_with_gemini(
        company_name, company_description, candidate_news, us_entities_for_prompt
    )
    if not selected_news_data:
        print("[News Analyst] Gemini로부터 유효한 뉴스 선택 결과를 받지 못했습니다.")
        return {"selected_news": []}
    
    # 4. Gemini 결과를 기반으로 최종 뉴스 목록 구성
    final_news_list: List[SelectedNews] = []
    for news_info in selected_news_data:
        index = news_info.get("index")
        related_tickers = news_info.get("related_tickers", [])
        
        if index is None or not (0 <= index < len(candidate_news)):
            continue
        
        news_item = candidate_news[index]
        
        # Ticker에 해당하는 이름을 찾아서 'entities' 필드에 저장
        entity_names = [v['name'] for k, v in METRICS_MAP.items() if k in related_tickers]

        selected_news_item: SelectedNews = {
            "title": news_item["title"],
            "url": news_item["url"],
            "summary": news_item["summary"],
            "entities": entity_names,                 # 사람/AI가 이해하는 이름
            "related_metrics": related_tickers,      # 기계가 사용할 Ticker/ID
        }
        final_news_list.append(selected_news_item)
        print(f"  - 뉴스 선별: \"{news_item['title']}\" (연관 Ticker: {related_tickers})")

    # 5. 분석된 결과를 상태(State)에 추가하여 반환
    return {"selected_news": final_news_list}
