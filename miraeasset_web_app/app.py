import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, current_app
from flask_socketio import SocketIO, emit
import sys
import threading
import time
from typing import Optional, List, Dict, Any

# 프로젝트 루트를 Python Path에 추가
# analysis_model의 함수들을 모듈로 임포트.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# .env 파일 로드
# env 파일을 제거하고, 환경변수를 직접 입력하였지만 코드의 연속성을 위해 남겨둠
load_dotenv()

# analysis_model의 AI 에이전트 함수들을 불러온다
from analysis_model.state import AnalysisState, MarketAnalysisResult
from analysis_model.agents.data_prep_agent import run_data_prep
from analysis_model.agents.news_analyst_agent import run_news_analyst
from analysis_model.agents.domestic_news_analyst_agent import run_domestic_news_analyst
from analysis_model.agents.market_correlation_agent import run_market_correlation
from analysis_model.agents.report_synthesizer_agent import run_report_synthesizer


# Flask 애플리케이션 및 SocketIO 초기화
# 에이전트간의 정보 공유를 위함
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

#######################################################################
# 포트폴리오

## 포트폴리오 파일 경로 설정
PORTFOLIO_FILE = 'portfolio.json'
## 포트폴리오 읽어오기
_cached_portfolio_initial_data = []
try:
    with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f: # json 데이터 불러오기
        _cached_portfolio_initial_data = json.load(f)
    print("✅ Initial portfolio data loaded successfully.")
except FileNotFoundError:
    print(f"경고: {PORTFOLIO_FILE} 파일을 찾을 수 없습니다. 포트폴리오 기능이 제한됩니다.")
except json.JSONDecodeError:
    print(f"오류: {PORTFOLIO_FILE} 파일이 유효한 JSON 형식이 아닙니다.")

#######################################################################
# 데이터베이스 접속
## 환경변수
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client_global = None # None으로 초기화하여 연결 실패 시에도 앱이 시작되도록 함

#######################################################################
# 기업건전성 보고서

_financial_statement_companies: List[Dict[str, str]] = [] # 'financial_statements' 테이블에서 가져온 기업 목록을 저장할 리스트
_financial_statement_tickers_set: set[str] = set() # 특정 티커가 분석 가능한지 빠르게 조회하기 위한 집합

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("경고: SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다. Supabase 연동 불가.")
else:
    from supabase import create_client, Client
    try:
        supabase_client_global: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized for app.py.")

        # 기업건전성 보고서가 있는 기업만 조회 (존재하는 기업만 분석을 가능하게하기 위함)
        def _initialize_financial_statement_cache():

            # 전역 변수로 생성
            global _financial_statement_companies
            global _financial_statement_tickers_set
            if supabase_client_global:
                try:
                    # 'financial_statements' 테이블에서 'ticker'와 'company_name' 컬럼을 조회
                    response = supabase_client_global.table("financial_statements").select("ticker, company_name").execute()
                    
                    temp_companies = [] # 기업 정보
                    temp_tickers_set = set()

                    for row in response.data: # 조회된 기업에 대하여
                        # 명시적으로 문자열로 변환하고 None/빈 문자열 처리
                        ticker_val = str(row.get('ticker')).strip() if row.get('ticker') is not None else None
                        name_val = str(row.get('company_name')).strip() if row.get('company_name') is not None else None

                        # ticker_val과 name_val이 모두 유효한 문자열인 경우에만 추가
                        if ticker_val and name_val:
                            temp_companies.append({'ticker': ticker_val, 'name': name_val})
                            temp_tickers_set.add(ticker_val)
                        else:
                            # 어떤 행이 유효하지 않은지 로그를 남겨 디버깅에 도움
                            print(f"Skipping financial_statements row due to missing/invalid ticker or company_name: {row}")

                    # 임시 변수에 저장했던 데이터를 전역 변수로 전달
                    _financial_statement_companies = temp_companies
                    _financial_statement_tickers_set = temp_tickers_set
                    print(f"✅ Loaded {len(_financial_statement_companies)} companies from financial_statements for search/analysis eligibility.")
                except Exception as e:
                    print(f"🚨 Failed to load financial statement companies cache: {e}")

                    ##오류 발생 시 초기화
                    _financial_statement_companies = []
                    _financial_statement_tickers_set = set()
        
        # Supabase에 접속하면 실행
        _initialize_financial_statement_cache()
        
    except Exception as e:
        print(f"🚨 Supabase 클라이언트 초기화 중 오류 발생: {e}")
        supabase_client_global = None

#######################################################################
# 티커 -> 기업/지표 명칭 반환

## 주요지표 목록 (_get_company_name_from_db와 search_stocks에서 사용)
COMMON_INDICES_CURRENCIES = {
    '^GSPC': 'S&P 500 Index',
    '^IXIC': 'NASDAQ Composite',
    '^DJI': 'Dow Jones Industrial Average',
    '^KS11': 'KOSPI Composite Index',
    '^KQ11': 'KOSDAQ Composite Index',
    '^NDX': "NASDAQ-100",
    'LIT': '리튬 ETF',
    '^TNX': '미국 10년물 국채 수익률',
    'NBI': '나스닥 바이오테크놀로지 지수',
    '^VIX': 'CBOE 변동성 지수',
    'CL=F': 'WTI 원유 선물',
    'FDN': '다우존스 인터넷 지수',
    'USDKRW=X': '달러/원 환율'
}


## 데이터베이스에서 회사, 주요지표 이름 조회 함수
def _get_company_name_from_db(ticker: str) -> Optional[str]:
    """
    Supabase에서 티커에 해당하는 회사 이름을 조회합니다.
    조회 우선순위 (분석 에이전트가 사용할 'company_name'을 위해 영문 이름 우선):
    1. 고정 지수/환율 이름 (UI 표시 목적)
    2. korean_stocks/us_stocks (분석 에이전트에게 필요한 영문 표준 이름)
    이 함수는 financial_statements 테이블의 이름을 분석 에이전트가 직접 사용하도록 반환하지 않습니다.
    """
    # 1. 주요지표 명칭 확인 (UI 표시 목적의 이름)
    if ticker in COMMON_INDICES_CURRENCIES:
        return COMMON_INDICES_CURRENCIES[ticker]

    if not supabase_client_global:
        return None # Supabase 연결 없으면 이름 조회 불가

    company_name_from_stocks = None # stocks 테이블에서 찾은 이름을 저장할 변수

    try:
        # 2. 한국 주식 테이블에서 영문 이름 조회
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            response_kr = supabase_client_global.table("korean_stocks").select("company_name").eq('ticker', ticker).limit(1).execute()
            if response_kr.data and response_kr.data[0].get('company_name'):
                company_name_from_stocks = response_kr.data[0]['company_name']
        # 3. 미국 주식 테이블에서 영문 이름 조회
        elif not (ticker.startswith('^') or ticker.endswith('=X')): # 주요지표인 경우를 제외(없어도 될거같은데)
            response_us = supabase_client_global.table("us_stocks").select("company_name").eq('ticker', ticker).limit(1).execute()
            if response_us.data and response_us.data[0].get('company_name'):
                company_name_from_stocks = response_us.data[0]['company_name']

        # 찾은 이름이 유효한지 확인하고 반환
        if company_name_from_stocks is not None and company_name_from_stocks.strip() != '':
            return company_name_from_stocks.strip()

    except Exception as e:
        print(f"🚨 Supabase에서 회사 이름 조회 중 오류 발생 (_get_company_name_from_db - stocks 테이블): {e}")

    # korean_stocks 또는 us_stocks에서 영문 이름을 찾지 못했으면 None 반환
    return None

#######################################################################
# 포트폴리오용 주가 불러오기
## 서비스가 시작될 시 자동 작동함
def get_stock_price_and_info(ticker: str, purchase_price: Optional[float] = None, quantity: Optional[int] = None) -> dict:
    """
    Supabase에서 현재 주가(close_price)를 가져오고 손익을 계산합니다.
    purchase_price와 quantity는 선택 사항으로 만들어서, 포트폴리오가 아닌 일반 주가 조회에도 사용 가능하게 합니다.
    """
    
    # 데이터베이스 접속에 실패했을 경우
    if not supabase_client_global:
        return {
            "ticker": ticker,
            "current_price": "N/A",
            "purchase_price": purchase_price,
            "quantity": quantity,
            "profit_loss_per_share": "N/A",
            "profit_loss_total": "N/A",
            "profit_loss_percentage": "N/A",
            "error": "Supabase 클라이언트가 초기화되지 않았습니다."
        }
        
    try:
        order_col = "time" # 날짜 저장
        ticker_filter_col = "ticker" # 티커 저장

        # 티커의 종류에 따라 조회할 테이블 설정 (한국 / 미국 주식)
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            table_name = "korean_stocks"
        elif not (ticker.startswith('^') or ticker.endswith('=X')): # 주요지표를 제외한 나머지 (없어도 될거같은데)
             table_name = "us_stocks"
        else: # 오류 발생 시
            print(f"Warning: Ticker '{ticker}' might be an index/currency, which is not fully supported by this price lookup function.")
            return {
                "ticker": ticker,
                "current_price": "N/A",
                "purchase_price": purchase_price,
                "quantity": quantity,
                "profit_loss_per_share": "N/A",
                "profit_loss_total": "N/A",
                "profit_loss_percentage": "N/A",
                "error": "This function is designed for stock tickers only (not indices/currencies)."
            }


        # 날짜 내림차순 -> 최신 데이터만 가져오기
        response = supabase_client_global.table(table_name).select("close_price").eq(ticker_filter_col, ticker).order(order_col, desc=True).limit(1).execute()
        
        data = response.data
        
        current_price = None
        if data and len(data) > 0 and 'close_price' in data[0]:
            current_price = data[0]['close_price']
            
        if current_price is None:
            # 가격을 찾지 못하면 에러 발생
            raise ValueError(f"'{ticker}'의 Supabase에서 현재 가격(close_price)을 찾을 수 없습니다.")

        # purchase_price와 quantity가 None이 아닐 때만 손익 계산
        if purchase_price is not None and quantity is not None:
            profit_loss_per_share = float(current_price) - purchase_price
            profit_loss_total = profit_loss_per_share * quantity
            profit_loss_percentage = (profit_loss_per_share / purchase_price) * 100 if purchase_price != 0 else 0
            
            return {
                "ticker": ticker,
                "current_price": round(float(current_price), 2),
                "purchase_price": purchase_price,
                "quantity": quantity,
                "profit_loss_per_share": round(profit_loss_per_share, 2),
                "profit_loss_total": round(profit_loss_total, 2),
                "profit_loss_percentage": round(profit_loss_percentage, 2)
            }
        else: # 포트폴리오 정보가 없을 때는 현재 가격만 반환
            return {
                "ticker": ticker,
                "current_price": round(float(current_price), 2),
                "purchase_price": None,
                "quantity": None,
                "profit_loss_per_share": None,
                "profit_loss_total": None,
                "profit_loss_percentage": None
            }

    except Exception as e:
        print(f"🚨 Supabase로 '{ticker}' 주식 정보 조회 중 오류 발생: {e}")
        return {
            "ticker": ticker,
            "current_price": "N/A",
            "purchase_price": purchase_price,
            "quantity": quantity,
            "profit_loss_per_share": "N/A",
            "profit_loss_total": "N/A",
            "profit_loss_percentage": "N/A",
            "error": str(e)
        }
#######################################################################
# Flask 라우트 설정

# 메인페이지
## 웹프론트엔드 구성
@app.route('/')
def index():
    """메인 페이지를 렌더링합니다."""
    return render_template('index.html')

## 서비스 시작 시 포트폴리오 구성
@app.route('/portfolio_summary', methods=['GET'])
def get_full_portfolio_summary():
    """모든 보유 주식의 현재가 및 손익을 계산하여 반환합니다."""
    full_summary = []
    total_purchase_value = 0
    total_current_value = 0
    
    # 포트폴리오 작성 (예시로 입력한 portfolio.json 파일을 사용)
    for stock_data in _cached_portfolio_initial_data:
        ticker = stock_data.get('ticker') # 티커
        purchase_price = stock_data.get('purchase_price', 0) # 구매가
        quantity = stock_data.get('quantity', 0) # 수량
        
        # UI 표시를 위한 이름은 portfolio.json 또는 financial_statements(기업건전성 보고서)에서 가져옴
        display_name = stock_data.get('name') 
        if not display_name or display_name == ticker: # portfolio.json에 이름이 없으면 financial_statements에서 가져옴
            for fs_company in _financial_statement_companies:
                if fs_company['ticker'] == ticker:
                    display_name = fs_company['name']
                    break
        if not display_name or display_name == ticker: # 명칭을 못가져오면 대신 티커로 사용
            display_name = ticker

        # 기업건전성 보고서를 가져올 수 있는지 확인 (없다면 포트폴리오의 기업을 분석 대상으로 삼지 못함)
        is_analyzable = ticker in _financial_statement_tickers_set
        
        # 각 주식의 상세 정보 및 손익 계산
        stock_summary = get_stock_price_and_info(ticker, purchase_price, quantity)
        stock_summary['name'] = display_name # UI 표시용 이름으로 설정
        stock_summary['is_analyzable'] = is_analyzable # 기업건전성 보고서를 가져올 수 있는지
        full_summary.append(stock_summary)

        # 총 자산 가치 계산 (숫자일 경우에만 합산)
        # N/A 값일 경우 합산에서 제외 (또는 0으로 간주)
        if isinstance(stock_summary['purchase_price'], (int, float)) and isinstance(stock_summary['quantity'], (int, float)):
             total_purchase_value += stock_summary['purchase_price'] * stock_summary['quantity']
        if isinstance(stock_summary['current_price'], (int, float)) and isinstance(stock_summary['quantity'], (int, float)):
            total_current_value += stock_summary['current_price'] * stock_summary['quantity']

    total_profit_loss = total_current_value - total_purchase_value
    total_profit_loss_percentage = (total_profit_loss / total_purchase_value) * 100 if total_purchase_value != 0 else 0

    # 계산한 포트폴리오 정보를 반환
    return jsonify({
        "stocks": full_summary,
        "total_portfolio_summary": {
            "total_purchase_value": round(total_purchase_value, 2),
            "total_current_value": round(total_current_value, 2),
            "total_profit_loss": round(total_profit_loss, 2),
            "total_profit_loss_percentage": round(total_profit_loss_percentage, 2)
        }
    })

# 기업, 주요지표 요약문 조회 (한글번역본)
@app.route('/stock_info/<ticker>', methods=['GET'])
def get_single_stock_info(ticker: str):
    """
    특정 티커의 현재 주가 정보와 회사 이름을 반환합니다.
    """

    # 데이터베이스 연결 실패할 경우
    if not supabase_client_global:
        return jsonify({"error": "Supabase 클라이언트가 초기화되지 않았습니다."}), 500

    try:
        # 1. 주요지표인 경우 'indices_summary' 테이블에서 조회
        if ticker in COMMON_INDICES_CURRENCIES:
            name_to_display = COMMON_INDICES_CURRENCIES[ticker]
            response = supabase_client_global.table("indices_summary").select("ko_summary").eq('ticker', ticker).single().execute()
            
            ko_summary = '이 지표에 대한 국문 설명이 없습니다.'
            if response.data:
                ko_summary = response.data.get('ko_summary', ko_summary)
            
            return jsonify({
                "name": name_to_display,
                "ko_summary": ko_summary
            })

        # 2. 기업인 경우 'company_summary' 테이블에서 조회
        else:
            response = supabase_client_global.table("company_summary").select("company_name, ko_summary").eq('ticker', ticker).single().execute()

            if response.data:
                return jsonify({
                    "name": response.data.get('company_name', ticker),
                    "ko_summary": response.data.get('ko_summary', '이 기업에 대한 국문 설명이 없습니다.')
                })
            else:
                # company_summary에 정보가 없을 경우를 대비한 대체 처리
                display_name = ticker
                for fs_company in _financial_statement_companies:
                    if fs_company['ticker'] == ticker:
                        display_name = fs_company['name']
                        break
                return jsonify({
                    "name": display_name,
                    "ko_summary": "이 기업에 대한 국문 설명이 없습니다."
                })

    except Exception as e:
        print(f"🚨 Supabase에서 '/stock_info/{ticker}' 조회 중 오류 발생: {e}")
        return jsonify({"error": f"데이터베이스 조회 중 오류 발생: {str(e)}"}), 500


## 분석 가능한 주식 목록 조회 (기업건전성 보고서가 존재하는지)
@app.route('/analyzable_stocks', methods=['GET'])
def get_analyzable_stocks_list():
    """
    재무제표 분석이 가능한 모든 기업의 티커와 이름을 반환합니다.
    (otherStockSelect 드롭다운을 채우는 데 사용됩니다.)
    """
    return jsonify(_financial_statement_companies) # 이미 캐시된 리스트 반환

#######################################################################
# SocketIO 이벤트 핸들러 설정

## SocketIO 연결 시 이벤트 핸들러

@socketio.on('connect') #연결
def test_connect():
    print('Client connected')
    emit('status_update', {'message': '서버에 연결되었습니다. 주식 분석을 시작하세요.', 'progress': 0})

@socketio.on('disconnect') #연결 끊음
def test_disconnect():
    print('Client disconnected')

@socketio.on('start_analysis_request') # 프론트엔드에서 분석 시작 요청을 받음
def handle_start_analysis_request(data):
    """
    클라이언트(웹 브라우저)로부터 'start_analysis_request' 이벤트를 수신합니다.
    이 이벤트는 사용자가 '분석 시작' 버튼을 클릭했을 때 발생합니다.
    """
    ticker = data.get('ticker') # 티커를 기준으로 분석 시작
    if not ticker:
        emit('status_update', {'message': '오류: 티커가 필요합니다.', 'progress': -1})
        return

    print(f"웹 요청: '{ticker}' 기업에 대한 전체 분석 파이프라인을 시작합니다.")
    
    # Flask 애플리케이션 컨텍스트를 수동으로 활성화하여 백그라운드 스레드에서 Flask 기능을 사용할 수 있게 함
    with app.app_context():
        # 기업건전성 보고서가 있는 기업인지 재차 확인
        if ticker not in _financial_statement_tickers_set:
            emit('status_update', {
                'message': f"'{ticker}' 기업은 재무제표 분석 데이터가 없어 전체 투자 브리핑을 제공할 수 없습니다.",
                'progress': -1
            })
            return

        threading.Thread(target=run_full_analysis_pipeline, args=(ticker, request.sid)).start()

#######################################################################
# AI 에이전트 파이프라인

# 파이프라인 실행 함수
def run_full_analysis_pipeline(ticker: str, sid: str):
    """
    전체 분석 파이프라인을 실행하고 진행 상황을 클라이언트에 emit합니다.
    """
    with app.app_context():
        # 기업명 불러오기
        company_name_for_analysis = _get_company_name_from_db(ticker)

        # company_name_for_analysis가 None이거나 빈 문자열이면 분석 중단
        if not company_name_for_analysis:
            error_msg = f"'{ticker}'에 대한 분석 가능한 영문 회사 이름을 찾을 수 없습니다. (Supabase의 korean_stocks/us_stocks 데이터 확인 필요)"
            print(f"🚨 {error_msg}")
            socketio.emit('status_update', {'message': error_msg, 'progress': -1}, room=sid)
            return


        # 데이터를 저정하고 전달할 AnalysisState 객체
        initial_state: AnalysisState = {
            "ticker": ticker, # 티커
            "company_name": company_name_for_analysis, # 기업명
            "company_description": None, # 기업설명문 (영어 - LLM용)
            "financial_health": None, # 기업건전성 보고서
            "selected_news": None, # 선택된 미국 금융뉴스
            "selected_domestic_news": None, # 선택된 국내 금융뉴스
            "market_analysis_result": None, # 주식 상관관계
            "final_report": None, # 최종보고서
            "historical_prices": None, # 주식 장기 데이터
            "news_event_markers": None, # 뉴스 관련 기업, 지표 (시각화용)
            "all_analyzed_tickers": None, # 뉴스 관련 티커 목록 (시각화용)
            "all_us_news": [], # 전체 미국 뉴스
            "all_domestic_news": [], # 전체 국내 뉴스
            "us_market_entities": [], # 해외 뉴스 관련 기업, 지표
            "domestic_market_entities": [], # 국내 뉴스 관련 기업, 지표
        }
        current_state = initial_state.copy()
        
        # portfolio_summary에 is_portfolio_holding 플래그 추가
        is_portfolio_holding = False
        selected_stock_portfolio_info = None
        for stock_data in _cached_portfolio_initial_data:
            if stock_data.get('ticker') == ticker:
                selected_stock_portfolio_info = stock_data
                is_portfolio_holding = True
                break
        portfolio_summary = {
            "ticker": ticker,
            "is_portfolio_holding": is_portfolio_holding
        }

        # 기업건전성 보고서가 존재한다면    
        if is_portfolio_holding:
            summary_from_db = get_stock_price_and_info(
                ticker,
                selected_stock_portfolio_info.get('purchase_price', 0),
                selected_stock_portfolio_info.get('quantity', 0)
            )
            portfolio_summary.update(summary_from_db)
            # 포트폴리오 요약의 이름은 portfolio.json에 있는 이름을 사용 (UI를 위해)
            portfolio_summary['name'] = selected_stock_portfolio_info.get('name') 
            # 만약 portfolio.json에 이름이 없으면 financial_statements 캐시에서 가져옴 (한국어일 수 있음)
            if not portfolio_summary['name'] or portfolio_summary['name'] == ticker:
                for fs_company in _financial_statement_companies:
                    if fs_company['ticker'] == ticker:
                        portfolio_summary['name'] = fs_company['name']
                        break
        else:
            # 포트폴리오에 없는 주식인 경우, 회사 이름은 UI 표시를 위해 financial_statements 캐시에서 가져옴
            display_name_from_fs = ticker
            for fs_company in _financial_statement_companies:
                if fs_company['ticker'] == ticker:
                    display_name_from_fs = fs_company['name']
                    break
            
            # 최소한의 정보만 제공하고, purchase_price, quantity 등은 None
            portfolio_summary.update({
                "message": "선택된 주식의 포트폴리오 정보(구매가, 수량)를 찾을 수 없습니다.",
                "name": display_name_from_fs, 
                "current_price": get_stock_price_and_info(ticker).get('current_price', 'N/A') # 현재 가격은 가져와서 표시
            })
            print(f"선택된 주식의 포트폴리오 정보(구매가, 수량)를 찾을 수 없습니다: {ticker}")


        try:
            # 1. 데이터 준비 (이제 run_data_prep은 이미 company_name이 설정된 상태의 state를 받음)
            socketio.emit('status_update', {'message': '데이터 준비 중...', 'progress': 10}, room=sid)
            time.sleep(1)
            updated_state_from_data_prep = run_data_prep(current_state)
            current_state.update(updated_state_from_data_prep)
            print("[백엔드] 데이터 준비 완료")

            # 이전의 `if not current_state.get('company_name')` 체크는 이제 거의 불필요하지만,
            # 혹시 `run_data_prep` 내부에서 이름을 `None`으로 덮어쓸 경우를 대비한 최종 방어.
            if not current_state.get('company_name'):
                error_msg = f"'{ticker}' 기업의 기본 정보(회사명)를 분석 중 잃었습니다."
                print(f"🚨 {error_msg}")
                socketio.emit('status_update', {'message': error_msg, 'progress': -1}, room=sid)
                return 

            # 2. 해외 뉴스 분석 (이제 AnalysisState.company_name이 영문(선호) 이름으로 전달됨)
            # 뉴스 에이전트는 이 company_name을 사용하여 Supabase 벡터 검색을 수행해야 함 -> 정상 작동
            socketio.emit('status_update', {'message': '해외 뉴스 분석 중...', 'progress': 30}, room=sid)
            time.sleep(1)
            updated_state_from_news = run_news_analyst(current_state) #RAG
            current_state.update(updated_state_from_news)
            print("[백엔드] 해외 뉴스 분석 완료")

            # 3. 국내 뉴스 분석 (동일)
            socketio.emit('status_update', {'message': '국내 뉴스 분석 중...', 'progress': 50}, room=sid)
            time.sleep(1)
            updated_state_from_domestic_news = run_domestic_news_analyst(current_state) #RAG
            current_state.update(updated_state_from_domestic_news)
            print("[백엔드] 국내 뉴스 분석 완료")

            # 4. 시장 데이터 분석
            # run_market_correlation은 티커를 기반으로 시계열 데이터를 가져오므로,
            # 이 단계에서 "시계열 데이터를 가져오지 못했습니다" 오류는 해당 티커의 가격 데이터가 DB에 없는 것임.
            socketio.emit('status_update', {'message': '시장 데이터 분석 중...', 'progress': 70}, room=sid)
            time.sleep(1)
            updated_state_from_market_correlation = run_market_correlation(current_state)
            current_state.update(updated_state_from_market_correlation)
            print("[백엔드] 시장 데이터 분석 완료")

            # market_analysis_result가 None인 경우 빈 사전으로 초기화
            if current_state.get('market_analysis_result') is None:
                current_state['market_analysis_result'] = {
                    "news_impact_data": [], 
                    "historical_prices": {}, 
                    "all_analyzed_tickers": [], 
                    "correlation_matrix": {}
                }
                print("⚠️ market_analysis_result가 None이어서 빈 사전으로 초기화합니다.")


            # 5. 최종 투자 브리핑 생성
            socketio.emit('status_update', {'message': '최종 투자 브리핑 생성 중...', 'progress': 90}, room=sid)
            time.sleep(1)
            updated_state_from_report_synthesizer = run_report_synthesizer(current_state)
            current_state.update(updated_state_from_report_synthesizer)
            print("[백엔드] 최종 투자 브리핑 생성 완료")

            # 프론트엔드에 출력할 데이터 전달
            final_report = current_state.get("final_report")
            selected_news_for_frontend = current_state.get("selected_news", [])
            selected_domestic_news_for_frontend = current_state.get("selected_domestic_news", [])
            
            # 새롭게 추가된 데이터 필드를 추출
            historical_prices = current_state.get("historical_prices", {}) # 장기 데이터
            short_term_prices = current_state.get("short_term_prices", {}) # 단기 데이터
            news_event_markers = current_state.get("news_event_markers", {}) # 기업, 지표명
            all_analyzed_tickers = current_state.get("all_analyzed_tickers", []) # 티커 목록
            
            # market_analysis_result에서 correlation_matrix 추출
            #### 이젠 사용하지 않음
            market_analysis_result = current_state.get("market_analysis_result", {})
            correlation_matrix = market_analysis_result.get("correlation_matrix", {})
            
            # 국문 기업 설명을 상태(state)에서 가져오가
            ko_company_description = current_state.get("ko_company_description", "기업 설명 정보를 불러오지 못했습니다.")

            if final_report:
                socketio.emit('analysis_complete', {
                    'report': final_report,
                    'portfolio_summary': portfolio_summary,
                    'selected_news': selected_news_for_frontend,
                    'selected_domestic_news': selected_domestic_news_for_frontend,
                    'historical_prices': historical_prices,
                    'short_term_prices': short_term_prices,
                    'news_event_markers': news_event_markers,
                    'all_analyzed_tickers': all_analyzed_tickers,
                    'correlation_matrix': correlation_matrix,
                    'ko_company_description': ko_company_description, # 국문 기업 설명문 (최종보고서용)
                    'message': '분석 완료!'
                }, room=sid)
            else:
                socketio.emit('status_update', {'message': '오류: 최종 보고서 생성 실패.', 'progress': -1}, room=sid)

        except Exception as e:
            print(f"🚨 분석 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            socketio.emit('status_update', {'message': f"분석 중 오류 발생: {str(e)}", 'progress': -1}, room=sid)

#######################################################################
# 애플리케이션 실행
if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0')