import json
import os
import webbrowser
from typing import List, Dict, Any, TypedDict
import datetime # 날짜 생성을 위함
import random   # 가상 데이터 생성을 위함

# Gemini API 관련 모듈 (데이터를 준비하는 예시 코드에 필요)
from google import genai
from google.genai import types
import traceback


# AnalysisState는 실제 프로젝트 구조에 따라 정의되어 있을 것이므로,
# 여기서는 간단히 TypedDict로 정의합니다.
# 실제 코드에서는 해당 모듈에서 임포트해야 합니다.
class AnalysisState(TypedDict):
    company_name: str
    ticker: str
    company_description: str
    financial_health: Any
    selected_news: List[Dict[str, Any]] # selected_news의 타입 명시
    market_analysis_result: Any
    final_report: Any


# select_top_news_with_gemini 함수 정의 (이 함수는 데이터를 준비하는 데 사용됩니다)
def select_top_news_with_gemini(
    company_name: str,
    company_description: str,
    news_list: List[Dict[str, str]],
    us_entities_for_prompt: List[str]
) -> List[Dict[str, Any]]:
    """
    Gemini AI를 사용하여 뉴스 3개를 선별하고, 관련된 미국 기업/지표의 티커를 추출합니다.
    """
    print(f"[News Analyst] {company_name}의 15개 뉴스 중 핵심 뉴스 3개를 선별합니다.")

    entities_prompt_list = ", ".join(f'"{item}"' for item in us_entities_for_prompt)

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
        "\n### US ENTITY LIST (Name (Ticker)) ###",
        f"[{entities_prompt_list}]",
        "\n### OUTPUT FORMAT EXAMPLE ###",
        "{\"selected_news\": [{\"index\": 1, \"related_tickers\": [\"NVDA\"]}, {\"index\": 2, \"related_tickers\": [\"^NDX\", \"USDKRW=X\"]}, {\"index\": 8, \"related_tickers\": [\"MSFT\"]}]}",
        "\n--- TARGET COMPANY NEWS LIST ---\n"
    ]

    for i, news in enumerate(news_list):
        prompt_parts.append(f"[{i}] Title: {news['title']}\nSummary: {news['summary']}\n")
    prompt = "\n".join(prompt_parts)

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

        client = genai.Client(api_key=api_key)
        model = "gemini-2.5-flash"
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])] 
        
        generate_content_config = types.GenerateContentConfig(
            thinking_config = types.ThinkingConfig(
                thinking_budget=-1,
            ),
            tools=[
                types.Tool(googleSearch=types.GoogleSearch()),
            ],
            response_mime_type="text/plain",
        )

        response_stream = client.models.generate_content_stream( 
            model=model, 
            contents=contents, 
            config=generate_content_config,
        )

        response_text = ""
        for chunk in response_stream:
            response_text += chunk.text
            
        print("\n" + "="*40)
        print(">>> Gemini API Raw Response (for Debugging) <<<")
        print(response_text)
        print("="*40 + "\n")

        try:
            if '```json' in response_text:
                start_marker = '```json'
                end_marker = '```'
                start_index = response_text.rfind(start_marker)
                
                if start_index != -1:
                    json_candidate = response_text[start_index + len(start_marker):]
                    end_index = json_candidate.find(end_marker)
                    if end_index != -1:
                        json_string = json_candidate[:end_index].strip()
                    else:
                        json_string = json_candidate.strip()
                else:
                    json_string = response_text.strip()
            else:
                start_index = response_text.find('{')
                end_index = response_text.rfind('}') + 1
                if start_index != -1 and end_index > start_index:
                    json_string = response_text[start_index:end_index]
                else:
                    raise ValueError("Could not find a valid JSON object structure in the response.")

            result = json.loads(json_string)
            
            if 'selected_news' not in result or not isinstance(result['selected_news'], list):
                 raise ValueError("JSON is valid, but the 'selected_news' key is missing or not a list.")

            print(f"Gemini가 성공적으로 파싱한 뉴스 정보: {result['selected_news']}")
            return result['selected_news']
            
        except (json.JSONDecodeError, IndexError, ValueError) as e:
            print(f"!!! [ERROR] Failed to parse JSON from Gemini's response. Reason: {e}")
            raise

    except Exception as e:
        print(f"Gemini API 호출 또는 응답 처리 중 에러 발생: {e}")
        fallback_result = [{"index": i, "related_tickers": []} for i in range(min(3, len(news_list)))]
        print(f"비상 모드: 가장 관련성 높은 뉴스 {len(fallback_result)}개를 임시로 선택합니다.")
        return fallback_result

# run_news_analyst 함수 (데이터를 준비하는 데 사용됩니다)
def run_news_analyst(state: AnalysisState, all_news_data: Dict[str, List[Dict[str, str]]], us_entities: List[str]) -> AnalysisState:
    """
    이 함수는 실제 뉴스 분석 로직을 포함합니다.
    여기서는 select_top_news_with_gemini를 호출하는 예시로 대체합니다.
    all_news_data: 각 기업별 전체 뉴스 데이터를 담은 딕셔너리
    """
    company_name = state["company_name"]
    ticker = state["ticker"]

    # 해당 기업의 전체 뉴스 리스트를 가져옴
    news_list_for_company = all_news_data.get(ticker, [])

    if not news_list_for_company:
        print(f"경고: {company_name} ({ticker})에 대한 뉴스 데이터가 없습니다.")
        state["selected_news"] = []
        return state

    try:
        selected_news_data = select_top_news_with_gemini(
            company_name=company_name,
            company_description=state["company_description"],
            news_list=news_list_for_company,
            us_entities_for_prompt=us_entities
        )
        state["selected_news"] = selected_news_data
    except Exception as e:
        print(f"run_news_analyst 내부에서 select_top_news_with_gemini 호출 실패: {e}")
        traceback.print_exc() # 오류 스택 트레이스 출력
        state["selected_news"] = [{"index": i, "related_tickers": []} for i in range(min(3, len(news_list_for_company)))] # 비상 모드
    
    return state


# 가상의 과거 성과 데이터 생성 함수
def _generate_mock_performance_data(days: int = 30, initial_percentage: float = 0.0, volatility: float = 0.01, trend: float = 0.001) -> List[Dict[str, Any]]:
    """
    지정된 일수 동안 가상의 상대적 수익률 데이터를 생성합니다.
    initial_percentage: 첫날의 수익률 (기본 0%)
    volatility: 일별 변동성 (예: 0.01 = 1%)
    trend: 일별 평균 변화량 (예: 0.001 = 0.1% 상승)
    """
    data = []
    current_date = datetime.date.today() - datetime.timedelta(days=days - 1)
    current_value = initial_percentage # % 값으로 시작 (예: 0%)

    for _ in range(days):
        # 수익률에 작은 무작위 변화와 트렌드 적용
        daily_change = (random.random() - 0.5) * volatility * 2 + trend
        current_value += daily_change
        
        # 너무 급격한 변화를 막기 위해 값 제한 (예: -20% ~ +20%)
        current_value = max(-20.0, min(20.0, current_value)) 

        data.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "value": round(current_value, 2) # 소수점 둘째 자리까지
        })
        current_date += datetime.timedelta(days=1)
    return data


def generate_portfolio_html_page(
    portfolio_companies_data: Dict[str, Dict[str, Any]],
    template_path: str = "portfolio_template.html",
    output_filename: str = "my_portfolio_with_news_display.html"
) -> str:
    """
    사용자 보유 주식 포트폴리오 및 클릭 시 뉴스 표시 기능을 갖춘 HTML 페이지를 생성합니다.
    주어진 HTML 템플릿 파일에 데이터를 주입하여 최종 HTML 파일을 만듭니다.

    Args:
        portfolio_companies_data (Dict[str, Dict[str, Any]]):
            각 티커를 키로 하고, 해당 기업의 이름, 선택된 뉴스, 전체 뉴스 목록,
            그리고 historical_performance(과거 수익률 데이터)를 포함하는 딕셔너리.
        template_path (str): HTML 템플릿 파일의 경로. 기본값은 "portfolio_template.html".
        output_filename (str): 생성될 HTML 파일의 이름. 기본값은 "my_portfolio_with_news_display.html"

    Returns:
        str: 생성된 HTML 페이지의 전체 내용 문자열 (파일 저장 성공 시).
    """
    print(f"🚀 HTML 페이지 '{output_filename}' 생성을 시작합니다...")

    # HTML 템플릿 파일 읽기
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_template = f.read()
    except FileNotFoundError:
        print(f"❌ 오류: HTML 템플릿 파일 '{template_path}'을(를) 찾을 수 없습니다.")
        return f"<html><body><h1>오류: 템플릿 파일이 없습니다. ({template_path})</h1></body></html>"
    except Exception as e:
        print(f"❌ 오류: HTML 템플릿 파일 '{template_path}' 읽기 실패: {e}")
        return f"<html><body><h1>오류: 템플릿 파일 읽기 실패.</h1></body></html>"

    # JavaScript에 임베드할 데이터를 JSON 문자열로 변환
    js_news_data_str = json.dumps(portfolio_companies_data, ensure_ascii=False, indent=2)

    # 템플릿의 플레이스홀더를 실제 데이터로 교체
    final_html_content = html_template.replace("{all_company_news_data_json}", js_news_data_str)

    # HTML 파일을 저장합니다.
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_html_content)
        print(f"✅ HTML 페이지가 '{output_filename}' 파일에 성공적으로 저장되었습니다.")
        
        # 파일 저장 후 웹 브라우저로 자동 열기
        abs_file_path = os.path.abspath(output_filename)
        webbrowser.open(f'file://{abs_file_path}')
        print(f"웹 브라우저로 '{abs_file_path}'를 열었습니다.")
        
        return final_html_content
    except IOError as io_err:
        print(f"❌ HTML 파일 저장 중 오류가 발생했습니다: {io_err}")
        return f"<html><body><h1>파일 저장 오류: {io_err}</h1></body></html>"
    except Exception as e:
        print(f"❌ HTML 페이지 생성 중 알 수 없는 오류 발생: {e}")
        return f"<html><body><h1>페이지 생성 오류: {e}</h1></body></html>"


# --- 실행 예시: 이 부분을 실행하여 HTML 파일을 만들고 자동으로 엽니다. ---
if __name__ == '__main__':
    # 1. 뉴스 데이터 준비 (news_analyst_agent가 생성한 final_news_list를 시뮬레이션)
    #    실제 환경에서는 이 데이터가 이미 분석되어 준비되어 있어야 합니다.
    #    여기서는 예시 데이터를 생성하기 위해 Gemini API 호출을 포함합니다.

    all_companies_full_news_data = {
        "NVDA": [
            {"title": "엔비디아, 새로운 AI 칩 공개", "summary": "엔비디아가 차세대 AI 프로세서를 발표하며 상당한 성능 향상을 약속했습니다."},
            {"title": "TSMC, 엔비디아 칩 생산 확대", "summary": "TSMC가 엔비디아의 수요에 맞춰 고급 반도체 생산을 늘릴 계획입니다."},
            {"title": "AMD, AI 가속기 시장 경쟁 심화", "summary": "AMD가 새로운 AI 가속기를 출시하며 엔비디아와의 경쟁을 예고했습니다."},
            {"title": "엔비디아 주가 사상 최고치 경신", "summary": "인공지능 붐에 힘입어 엔비디아 주가가 사상 최고치를 기록했습니다."},
            {"title": "미국 규제, AI 칩 수출 제한 가능성", "summary": "미국 정부가 AI 칩 수출에 대한 추가 규제를 검토 중이라는 소식이 전해졌습니다."},
            {"title": "엔비디아, 자율주행 플랫폼 파트너십 확장", "summary": "엔비디아가 여러 자동차 회사들과 자율주행 기술 협력을 강화하고 있습니다."},
            {"title": "인텔, 파운드리 사업 확장", "summary": "인텔이 파운드리 사업을 확장하여 TSMC와 엔비디아에 도전장을 내밀었습니다."},
            {"title": "클라우드 서비스 기업, 엔비디아 GPU 대량 구매", "summary": "주요 클라우드 서비스 제공업체들이 AI 인프라 구축을 위해 엔비디아 GPU를 대량으로 구매하고 있습니다."},
            {"title": "엔비디아, 메타버스 관련 특허 출원 증가", "summary": "메타버스 분야에서 엔비디아의 기술 특허 출원이 꾸준히 늘고 있습니다."},
            {"title": "기술주 전반 하락, 엔비디아도 영향", "summary": "미국 기술주 전반의 조정으로 엔비디아 주가도 일시적으로 하락했습니다."},
            {"title": "새로운 게이밍 GPU 출시 임박", "summary": "엔비디아의 새로운 게이밍 GPU 라인업 출시가 임박했다는 소문이 돌고 있습니다."},
            {"title": "ARM, AI 칩 시장 진출 모색", "summary": "ARM이 자체 AI 칩 설계를 통해 엔비디아 시장에 진입할 계획입니다."},
            {"title": "AI 반도체 수요 폭발적 증가", "summary": "글로벌 AI 반도체 시장이 예상보다 빠르게 성장하고 있습니다."},
            {"title": "엔비디아, 소프트웨어 생태계 강화", "summary": "하드웨어와 더불어 쿠다(CUDA) 등 소프트웨어 플랫폼을 강화하고 있습니다."},
            {"title": "중국 시장, 엔비디아 칩 대체 움직임", "summary": "미중 갈등으로 중국 기업들이 엔비디아 칩 대체품을 찾고 있다는 보도입니다."},
        ],
        "AAPL": [
            {"title": "애플, 새로운 아이폰 16 발표", "summary": "애플이 가을 이벤트에서 새로운 아이폰 16 모델을 공개했습니다."},
            {"title": "애플 서비스 매출 급증", "summary": "앱스토어, 애플 뮤직 등 서비스 부문 매출이 크게 증가하여 실적을 견인했습니다."},
            {"title": "유럽연합, 애플 앱스토어 정책 조사", "summary": "EU가 디지털 시장법(DMA) 위반 여부에 대해 애플 앱스토어를 조사 중입니다."},
            {"title": "애플 워치, 건강 모니터링 기능 강화", "summary": "차세대 애플 워치에 더욱 정교한 건강 모니터링 기능이 탑재될 예정입니다."},
            {"title": "중국 시장 아이폰 판매 부진 우려", "summary": "경쟁 심화와 경제 둔화로 중국 내 아이폰 판매가 어려움을 겪고 있습니다."},
            {"title": "애플, AI 전략 구체화", "summary": "애플이 온디바이스 AI 기능을 강화하는 새로운 iOS 업데이트를 발표했습니다."},
            {"title": "비전 프로, 글로벌 출시 임박", "summary": "애플의 공간 컴퓨팅 기기 비전 프로의 글로벌 출시가 가까워졌습니다."},
            {"title": "맥북, 새로운 M4 칩 탑재", "summary": "애플이 M4 칩을 탑재한 새로운 맥북 라인업을 선보였습니다."},
            {"title": "애플 뮤직, 공간 오디오 기능 확대", "summary": "애플 뮤직이 지원하는 공간 오디오 트랙 수가 대폭 늘어났습니다."},
            {"title": "아이패드 프로, OLED 디스플레이 적용", "summary": "새로운 아이패드 프로 모델에 고품질 OLED 디스플레이가 적용될 예정입니다."},
            {"title": "애플, 자율주행차 프로젝트 재조정", "summary": "애플의 자율주행차 프로젝트 '타이탄'이 내부적으로 방향을 재조정하고 있습니다."},
            {"title": "주요 애널리스트, 애플 주가 목표치 상향", "summary": "일부 투자은행이 애플의 실적 전망치를 높이며 목표 주가를 상향했습니다."},
            {"title": "애플, 재생 에너지 투자 확대", "summary": "환경 경영의 일환으로 재생 에너지 발전소에 대한 투자를 늘리고 있습니다."},
            {"title": "서비스 구독자 수 10억 명 돌파", "summary": "애플의 유료 서비스 구독자 수가 전 세계적으로 10억 명을 넘어섰습니다."},
            {"title": "글로벌 스마트폰 시장 경쟁 심화", "summary": "삼성, 샤오미 등 경쟁사들의 신제품 출시로 스마트폰 시장 경쟁이 뜨거워지고 있습니다."},
        ],
        "MSFT": [
            {"title": "마이크로소프트, 코파일럿 스튜디오 공개", "summary": "마이크로소프트가 기업용 AI 도구 '코파일럿 스튜디오'를 발표했습니다."},
            {"title": "애저 클라우드 매출, 두 자릿수 성장 유지", "summary": "마이크로소프트의 클라우드 서비스 애저가 강력한 성장세를 이어가고 있습니다."},
            {"title": "마이크로소프트, 게임 스튜디오 인수 완료", "summary": "대형 게임 스튜디오 인수를 최종 완료하며 게임 부문을 강화했습니다."},
            {"title": "AI 기술, 윈도우 12에 통합될 예정", "summary": "차세대 윈도우 운영체제에 AI 기능이 대규모로 통합될 것으로 예상됩니다."},
            {"title": "사티아 나델라 CEO, AI 시대 비전 제시", "summary": "사티아 나델라 CEO가 인공지능이 가져올 미래 컴퓨팅 환경에 대한 비전을 발표했습니다."},
            {"title": "클라우드 보안 시장 경쟁 심화", "summary": "AWS, 구글 등과의 클라우드 보안 시장 경쟁이 더욱 치열해지고 있습니다."},
            {"title": "마이크로소프트 팀즈 사용자 3억 명 돌파", "summary": "협업 도구 마이크로소프트 팀즈의 월간 활성 사용자 수가 3억 명을 넘어섰습니다."},
            {"title": "오픈AI와의 협력, 새로운 AI 모델 개발", "summary": "오픈AI와의 파트너십을 통해 더욱 강력한 AI 모델을 공동 개발 중입니다."},
            {"title": "링크드인, AI 기반 채용 기능 도입", "summary": "링크드인이 AI를 활용한 맞춤형 채용 및 구직 기능을 선보였습니다."},
            {"title": "마이크로소프트 365, 생산성 향상 AI 기능 추가", "summary": "오피스 제품군에 AI 기반의 문서 작성 및 데이터 분석 기능이 추가되었습니다."},
            {"title": "Xbox 게임 패스, 구독자 수 지속 증가", "summary": "게임 구독 서비스 Xbox 게임 패스의 글로벌 구독자 수가 꾸준히 늘고 있습니다."},
            {"title": "데이터센터 인프라 투자 확대", "summary": "글로벌 AI 수요 증가에 맞춰 데이터센터 인프라 투자를 대폭 늘리고 있습니다."},
            {"title": "챗봇 기술, 고객 서비스에 적용", "summary": "마이크로소프트의 챗봇 기술이 기업 고객 서비스 솔루션에 활발히 적용되고 있습니다."},
            {"title": "시장 점유율, 엔터프라이즈 소프트웨어 분야 압도적", "summary": "마이크로소프트가 엔터프라이즈 소프트웨어 시장에서 압도적인 점유율을 유지하고 있습니다."},
            {"title": "신흥 시장, 클라우드 서비스 도입 가속화", "summary": "인도, 동남아 등 신흥 시장에서 마이크로소프트 클라우드 서비스 도입이 빠르게 증가하고 있습니다."},
            ]
    }

    example_us_entities = [
        "NVIDIA (NVDA)", "S&P 500 (^SPX)", "NASDAQ 100 (^NDX)", 
        "Microsoft (MSFT)", "Apple (AAPL)", "Alphabet (GOOGL)",
        "Amazon (AMZN)", "Meta Platforms (META)", "Tesla (TSLA)",
        "Intel (INTC)", "Qualcomm (QCOM)", "Taiwan Semiconductor Manufacturing (TSM)",
        "US Dollar / Korean Won (USDKRW=X)", "Crude Oil (CL=F)", "Gold (GC=F)"
    ]

    # 포트폴리오에 있는 회사들 (테스트용)
    portfolio_companies_initial_states: List[AnalysisState] = [
        {
            "company_name": "엔비디아", "ticker": "NVDA",
            "company_description": "엔비디아는 인공지능(AI), 고성능 컴퓨팅(HPC), 게이밍, 자율주행차 등을 위한 그래픽 처리 장치(GPU)와 관련 시스템 온 어 칩(SoC)을 설계 및 제조하는 선도적인 기술 기업입니다.",
            "financial_health": None, "selected_news": [], "market_analysis_result": None, "final_report": None,
        },
        {
            "company_name": "애플", "ticker": "AAPL",
            "company_description": "애플은 스마트폰(아이폰), 개인용 컴퓨터(맥), 태블릿(아이패드), 웨어러블 기기 및 액세서리(애플 워치, 에어팟) 등을 설계, 제조, 판매하는 세계적인 기술 기업입니다.",
            "financial_health": None, "selected_news": [], "market_analysis_result": None, "final_report": None,
        },
        {
            "company_name": "마이크로소프트", "ticker": "MSFT",
            "company_description": "마이크로소프트는 소프트웨어, 서비스, 장치 및 솔루션을 개발, 제조, 라이선스, 지원 및 판매하는 글로벌 기업입니다. 주요 제품으로는 윈도우, 오피스, 애저 클라우드 등이 있습니다.",
            "financial_health": None, "selected_news": [], "market_analysis_result": None, "final_report": None,
        },
    ]

    # 각 기업에 대해 뉴스 분석 실행하여 최종 데이터 구조를 만듭니다.
    # 이 'final_processed_portfolio_data'가 사용자가 'news_analyst_agent'로 생성했다고 가정한 데이터입니다.
    final_processed_portfolio_data = {} 
    for state in portfolio_companies_initial_states:
        try:
            print(f"\n--- {state['company_name']} ({state['ticker']}) 뉴스 분석 시작 ---")
            updated_state = run_news_analyst(state, all_companies_full_news_data, example_us_entities)
            
            # 가상의 과거 성과 데이터 추가
            mock_historical_performance = _generate_mock_performance_data(
                days=90, # 3개월치 데이터
                initial_percentage=random.uniform(-5.0, 5.0), # 시작 수익률 무작위
                volatility=random.uniform(0.005, 0.02), # 변동성 무작위
                trend=random.uniform(-0.0005, 0.001) # 트렌드 무작위
            )

            final_processed_portfolio_data[state['ticker']] = {
                "company_name": state['company_name'],
                "selected_news": updated_state['selected_news'],
                "full_news_list": all_companies_full_news_data.get(state['ticker'], []), # 해당 기업의 전체 뉴스
                "historical_performance": mock_historical_performance # 과거 성과 데이터 추가
            }
            print(f"--- {state['company_name']} ({state['ticker']}) 뉴스 분석 완료 ---")

        except Exception as e:
            print(f"❌ {state['company_name']} ({state['ticker']}) 뉴스 분석 중 오류 발생: {e}")
            traceback.print_exc() # 오류 스택 트레이스 출력
            final_processed_portfolio_data[state['ticker']] = {
                "company_name": state['company_name'],
                "selected_news": [], # 오류 시 빈 리스트
                "full_news_list": all_companies_full_news_data.get(state['ticker'], []),
                "historical_performance": _generate_mock_performance_data(days=90, initial_percentage=0.0) # 오류 시 기본 가상 데이터
            }

    # 2. 준비된 데이터를 바탕으로 HTML 페이지 생성 및 자동 열기
    generate_portfolio_html_page(
        portfolio_companies_data=final_processed_portfolio_data,
        template_path="portfolio_template.html", # 템플릿 파일 경로 지정
        output_filename="my_portfolio_with_news_display.html"
    )

    print("\n✅ 모든 작업이 완료되었습니다. 웹 브라우저를 확인해주세요.")