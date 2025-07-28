import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, current_app
from flask_socketio import SocketIO, emit
import sys
import threading
import time
from typing import Optional, List, Dict, Any

# 프로젝트 루트를 Python Path에 추가하여 analysis_model을 모듈로 임포트할 수 있게 합니다.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# .env 파일 로드 (가장 먼저 실행)
load_dotenv()

# analysis_model의 핵심 로직을 임포트합니다.
from analysis_model.state import AnalysisState, MarketAnalysisResult
from analysis_model.agents.data_prep_agent import run_data_prep
from analysis_model.agents.news_analyst_agent import run_news_analyst
from analysis_model.agents.domestic_news_analyst_agent import run_domestic_news_analyst
from analysis_model.agents.market_correlation_agent import run_market_correlation
from analysis_model.agents.report_synthesizer_agent import run_report_synthesizer


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 포트폴리오 파일 경로 설정
PORTFOLIO_FILE = 'portfolio.json'

_cached_portfolio_initial_data = []
try:
    with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
        _cached_portfolio_initial_data = json.load(f)
    print("✅ Initial portfolio data loaded successfully.")
except FileNotFoundError:
    print(f"경고: {PORTFOLIO_FILE} 파일을 찾을 수 없습니다. 포트폴리오 기능이 제한됩니다.")
except json.JSONDecodeError:
    print(f"오류: {PORTFOLIO_FILE} 파일이 유효한 JSON 형식이 아닙니다.")


# Supabase 접속 정보는 app.py에서도 필요합니다. (analysis_model 내부와 별개)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client_global = None # None으로 초기화하여 연결 실패 시에도 앱이 시작되도록 함

# NEW: 재무제표 분석 가능한 기업 정보를 캐싱할 전역 변수
_financial_statement_companies: List[Dict[str, str]] = [] # [{'ticker': 'AAPL', 'name': 'Apple Inc.'}, ...]
_financial_statement_tickers_set: set[str] = set() # 빠른 조회를 위한 티커 집합

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("경고: SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다. Supabase 연동 불가.")
else:
    from supabase import create_client, Client
    try:
        supabase_client_global: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized for app.py.")

        # NEW: 재무제표 분석 기업 목록을 초기화하고 캐싱하는 함수 (더욱 견고하게 수정)
        def _initialize_financial_statement_cache():
            global _financial_statement_companies
            global _financial_statement_tickers_set
            if supabase_client_global:
                try:
                    # 'financial_statements' 테이블에서 티커와 회사 이름을 가져옴
                    response = supabase_client_global.table("financial_statements").select("ticker, company_name").execute()
                    
                    temp_companies = []
                    temp_tickers_set = set()

                    for row in response.data:
                        # 명시적으로 문자열로 변환하고 None/빈 문자열 처리
                        ticker_val = str(row.get('ticker')).strip() if row.get('ticker') is not None else None
                        name_val = str(row.get('company_name')).strip() if row.get('company_name') is not None else None

                        # ticker_val과 name_val이 모두 유효한 (None이 아니고 비어있지 않은) 문자열인 경우에만 추가
                        if ticker_val and name_val:
                            temp_companies.append({'ticker': ticker_val, 'name': name_val})
                            temp_tickers_set.add(ticker_val)
                        else:
                            # 어떤 행이 유효하지 않은지 로그를 남겨 디버깅에 도움
                            print(f"⚠️ Skipping financial_statements row due to missing/invalid ticker or company_name: {row}")

                    _financial_statement_companies = temp_companies
                    _financial_statement_tickers_set = temp_tickers_set
                    print(f"✅ Loaded {len(_financial_statement_companies)} companies from financial_statements for search/analysis eligibility.")
                except Exception as e:
                    print(f"🚨 Failed to load financial statement companies cache: {e}")
                    _financial_statement_companies = []
                    _financial_statement_tickers_set = set()
        
        # Supabase 클라이언트 초기화 성공 시 캐시 로드
        _initialize_financial_statement_cache()
        
    except Exception as e:
        print(f"🚨 Supabase 클라이언트 초기화 중 오류 발생: {e}")
        supabase_client_global = None


# NEW: 공통 지수/환율 이름 목록 (_get_company_name_from_db와 search_stocks에서 사용)
COMMON_INDICES_CURRENCIES = {
    '^GSPC': 'S&P 500 Index',
    '^IXIC': 'NASDAQ Composite',
    '^DJI': 'Dow Jones Industrial Average',
    '^KS11': 'KOSPI Composite Index',
    '^KQ11': 'KOSDAQ Composite Index',
    'USDKRW=X': 'USD/KRW 환율',
    'JPYKRW=X': 'JPY/KRW 환율',
    'EURKRW=X': 'EUR/KRW 환율',
}


# 🚨 재수정된 부분: _get_company_name_from_db 함수 로직 변경 (영문 이름 최우선, financial_statements는 fallback 아님)
def _get_company_name_from_db(ticker: str) -> Optional[str]:
    """
    Supabase에서 티커에 해당하는 회사 이름을 조회합니다.
    조회 우선순위:
    1. 고정 지수/환율 이름 (분석 에이전트에서는 티커로 사용되나, UI 표시용 이름)
    2. korean_stocks/us_stocks (분석에 선호되는 영문 표준 이름)
    이 함수는 분석 에이전트가 사용할 '회사 이름'을 가져오는 데 초점을 맞춥니다.
    따라서 financial_statements의 이름은 여기서 고려하지 않습니다.
    """
    # 1. 고정된 지수/환율 이름 확인 (UI 표시 목적의 이름)
    if ticker in COMMON_INDICES_CURRENCIES:
        return COMMON_INDICES_CURRENCIES[ticker]

    if not supabase_client_global:
        return None # Supabase 연결 없으면 이름 조회 불가

    company_name_from_stocks = None # stocks 테이블에서 찾은 이름을 저장할 변수

    try:
        # 2. 한국 주식 테이블에서 영문 이름 조회 (우선 순위 높음)
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            response_kr = supabase_client_global.table("korean_stocks").select("company_name").eq('ticker', ticker).limit(1).execute()
            if response_kr.data and response_kr.data[0].get('company_name'):
                company_name_from_stocks = response_kr.data[0]['company_name']
        # 3. 미국 주식 테이블에서 영문 이름 조회 (우선 순위 높음)
        elif not (ticker.startswith('^') or ticker.endswith('=X')): # 지수/환율이 아닌 일반 주식인 경우
            response_us = supabase_client_global.table("us_stocks").select("company_name").eq('ticker', ticker).limit(1).execute()
            if response_us.data and response_us.data[0].get('company_name'):
                company_name_from_stocks = response_us.data[0]['company_name']

        # 찾은 이름이 유효한지 확인하고 반환
        if company_name_from_stocks is not None and company_name_from_stocks.strip() != '':
            return company_name_from_stocks.strip()

    except Exception as e:
        print(f"🚨 Supabase에서 회사 이름 조회 중 오류 발생 (_get_company_name_from_db - stocks 테이블): {e}")

    # korean_stocks 또는 us_stocks에서 영문 이름을 찾지 못했으면 None 반환
    # financial_statements의 이름은 '분석' 목적에서는 사용하지 않음
    return None


def get_stock_price_and_info(ticker: str, purchase_price: Optional[float] = None, quantity: Optional[int] = None) -> dict:
    """
    Supabase에서 현재 주가(close_price)를 가져오고 손익을 계산합니다.
    purchase_price와 quantity는 선택 사항으로 만들어서, 포트폴리오가 아닌 일반 주가 조회에도 사용 가능하게 합니다.
    """
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
        order_col = "time" # Default for stocks
        ticker_filter_col = "ticker" # Default for stocks

        # 한국/미국 주식 테이블 선택 로직 개선 (지수/환율은 이 함수에서 직접 조회하지 않음)
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            table_name = "korean_stocks"
        elif not (ticker.startswith('^') or ticker.endswith('=X')): # 지수/환율 제외한 나머지 (미국 주식으로 가정)
             table_name = "us_stocks"
        else: # 이 함수는 주식 티커에만 사용되어야 함
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


        # 가장 최신 close_price를 가져오기 위해 'time' 기준으로 정렬하여 1개만 가져옵니다.
        # 🚨 여기서 '시계열 데이터를 가져오지 못했습니다' 오류가 나는 경우, 해당 테이블에 해당 티커의 가격 데이터가 없는 것임
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

@app.route('/')
def index():
    """메인 페이지를 렌더링합니다."""
    return render_template('index.html')

@app.route('/portfolio_summary', methods=['GET'])
def get_full_portfolio_summary():
    """모든 보유 주식의 현재가 및 손익을 계산하여 반환합니다."""
    full_summary = []
    total_purchase_value = 0
    total_current_value = 0
    
    for stock_data in _cached_portfolio_initial_data:
        ticker = stock_data.get('ticker')
        purchase_price = stock_data.get('purchase_price', 0)
        quantity = stock_data.get('quantity', 0)
        
        # UI 표시를 위한 이름은 portfolio.json 또는 financial_statements에서 가져옴
        display_name = stock_data.get('name') 
        if not display_name or display_name == ticker: # portfolio.json에 이름이 없으면 financial_statements에서 가져옴
            for fs_company in _financial_statement_companies:
                if fs_company['ticker'] == ticker:
                    display_name = fs_company['name']
                    break
        if not display_name or display_name == ticker: # 그래도 없으면 티커 사용
            display_name = ticker

        # NEW: 이 티커에 대해 재무제표 분석이 가능한지 확인
        is_analyzable = ticker in _financial_statement_tickers_set
        
        # 각 주식의 상세 정보 및 손익 계산
        stock_summary = get_stock_price_and_info(ticker, purchase_price, quantity)
        stock_summary['name'] = display_name # UI 표시용 이름으로 설정
        stock_summary['is_analyzable'] = is_analyzable # NEW: is_analyzable 플래그 추가
        full_summary.append(stock_summary)

        # 총 자산 가치 계산 (숫자일 경우에만 합산)
        # N/A 값일 경우 합산에서 제외 (또는 0으로 간주)
        if isinstance(stock_summary['purchase_price'], (int, float)) and isinstance(stock_summary['quantity'], (int, float)):
             total_purchase_value += stock_summary['purchase_price'] * stock_summary['quantity']
        if isinstance(stock_summary['current_price'], (int, float)) and isinstance(stock_summary['quantity'], (int, float)):
            total_current_value += stock_summary['current_price'] * stock_summary['quantity']

    total_profit_loss = total_current_value - total_purchase_value
    total_profit_loss_percentage = (total_profit_loss / total_purchase_value) * 100 if total_purchase_value != 0 else 0

    return jsonify({
        "stocks": full_summary,
        "total_portfolio_summary": {
            "total_purchase_value": round(total_purchase_value, 2),
            "total_current_value": round(total_current_value, 2),
            "total_profit_loss": round(total_profit_loss, 2),
            "total_profit_loss_percentage": round(total_profit_loss_percentage, 2)
        }
    })

# --- 개별 주식 정보 조회 엔드포인트 (수정됨: 헬퍼 함수 호출) ---
@app.route('/stock_info/<ticker>', methods=['GET'])
def get_single_stock_info(ticker: str):
    """
    특정 티커의 현재 주가 정보와 회사 이름을 반환합니다. (포트폴리오 정보 없이)
    """
    stock_info = get_stock_price_and_info(ticker, purchase_price=None, quantity=None)
    
    # 헬퍼 함수를 사용하여 회사 이름 조회 (이름이 None일 수 있음)
    company_name_from_stocks = _get_company_name_from_db(ticker)
    
    # UI 표시용 이름은 stocks 테이블에서 가져온 이름이 없으면 financial_statements에서 가져옴
    display_name = company_name_from_stocks
    if not display_name or display_name == ticker: # stocks 테이블에 이름 없으면 financial_statements 캐시에서 가져옴
        for fs_company in _financial_statement_companies:
            if fs_company['ticker'] == ticker:
                display_name = fs_company['name']
                break
    if not display_name or display_name == ticker: # 그래도 없으면 티커 사용
        display_name = ticker

    stock_info['name'] = display_name # UI 표시용 이름으로 설정
    
    return jsonify(stock_info)


# NEW: 주식 검색 엔드포인트 (재무제표 기업 내에서만 검색)
@app.route('/search_stocks', methods=['GET'])
def search_stocks():
    query = request.args.get('query', '').strip().lower() # 쿼리를 소문자로 변환하여 대소문자 구분 없이 매칭
    if not query:
        return jsonify([])

    results = []
    MAX_SEARCH_RESULTS = 20 # 반환할 최대 검색 결과 수

    # 재무제표 분석 가능한 기업 캐시 내에서만 검색
    unique_results = {}
    for company_info in _financial_statement_companies: # 미리 캐싱된 목록 순회 (이름은 financial_statements 기준)
        ticker = company_info['ticker']
        name = company_info['name'] # 이 name은 financial_statements에 있는 이름 (한국어일 수 있음)

        if query in ticker.lower() or query in name.lower():
            # 검색 결과에는 financial_statements에 있는 이름과 티커를 그대로 반환
            unique_results[ticker] = {'ticker': ticker, 'name': name}
            if len(unique_results) >= MAX_SEARCH_RESULTS:
                break # 최대 결과 수 도달 시 중지

    results = list(unique_results.values())
    final_results = sorted(results, key=lambda x: x['name'])[:MAX_SEARCH_RESULTS]
    
    return jsonify(final_results)


# SocketIO 연결 시 이벤트 핸들러
@socketio.on('connect')
def test_connect():
    print('Client connected')
    emit('status_update', {'message': '서버에 연결되었습니다. 주식 분석을 시작하세요.', 'progress': 0})

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

@socketio.on('start_analysis_request') # 프론트엔드에서 분석 시작 요청을 받습니다.
def handle_start_analysis_request(data):
    ticker = data.get('ticker')
    if not ticker:
        emit('status_update', {'message': '오류: 티커가 필요합니다.', 'progress': -1})
        return

    print(f"🚀 웹 요청: '{ticker}' 기업에 대한 전체 분석 파이프라인을 시작합니다.")
    
    # Flask 애플리케이션 컨텍스트를 수동으로 활성화하여 백그라운드 스레드에서 Flask 기능을 사용할 수 있게 함
    with app.app_context():
        # NEW: 분석 가능 여부 다시 한번 확인 (이중 검증)
        if ticker not in _financial_statement_tickers_set:
            emit('status_update', {
                'message': f"'{ticker}' 기업은 재무제표 분석 데이터가 없어 전체 투자 브리핑을 제공할 수 없습니다.",
                'progress': -1
            })
            return

        threading.Thread(target=run_full_analysis_pipeline, args=(ticker, request.sid)).start()


def run_full_analysis_pipeline(ticker: str, sid: str):
    """
    전체 분석 파이프라인을 실행하고 진행 상황을 클라이언트에 emit합니다.
    """
    with app.app_context():
        # 🚨 NEW: 파이프라인 시작 시점에 company_name을 명시적으로 가져와서 초기 상태에 설정
        # _get_company_name_from_db가 이제 stocks 테이블에서 영문 이름만 우선적으로 가져옴.
        company_name_for_analysis = _get_company_name_from_db(ticker)

        # company_name_for_analysis가 None이거나 빈 문자열이면 분석 중단
        if not company_name_for_analysis: # None 또는 빈 문자열 체크
            error_msg = f"'{ticker}'에 대한 분석 가능한 영문 회사 이름을 찾을 수 없습니다. (Supabase의 korean_stocks/us_stocks 데이터 확인 필요)"
            print(f"🚨 {error_msg}")
            socketio.emit('status_update', {'message': error_msg, 'progress': -1}, room=sid)
            return # 필수 정보 없으므로 파이프라인 중단


        initial_state: AnalysisState = {
            "ticker": ticker,
            "company_name": company_name_for_analysis, # 🚨 이제 company_name은 여기서 영문(선호) 이름으로 초기화됨
            "company_description": None,
            "financial_health": None,
            "selected_news": None,
            "selected_domestic_news": None,
            "market_analysis_result": None, # run_market_correlation에서 채워질 예정
            "final_report": None,
            "historical_prices": None,
            "news_event_markers": None,
            "all_analyzed_tickers": None,
            "all_us_news": [],
            "all_domestic_news": [],
            "us_market_entities": [],
            "domestic_market_entities": [],
        }
        current_state = initial_state.copy()
        
        # 선택된 주식의 포트폴리오 정보 찾기 (기존 로직 유지)
        selected_stock_portfolio_info = None
        for stock_data in _cached_portfolio_initial_data:
            if stock_data.get('ticker') == ticker:
                selected_stock_portfolio_info = stock_data
                break

        portfolio_summary = {} # 단일 주식 요약 정보
        if selected_stock_portfolio_info:
            portfolio_summary = get_stock_price_and_info(
                ticker,
                selected_stock_portfolio_info.get('purchase_price', 0),
                selected_stock_portfolio_info.get('quantity', 0)
            )
            # 포트폴리오 요약의 이름은 portfolio.json에 있는 이름을 사용 (UI 목적)
            portfolio_summary['name'] = selected_stock_portfolio_info.get('name') 
            # 만약 portfolio.json에 이름이 없으면 financial_statements 캐시에서 가져옴
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

            portfolio_summary = {
                "ticker": ticker,
                "message": "선택된 주식의 포트폴리오 정보(구매가, 수량)를 찾을 수 없습니다.",
                "name": display_name_from_fs # financial_statements에서 가져온 이름 (한국어일 수 있음)
            }
            print(portfolio_summary['message'])


        try:
            # 1. 데이터 준비 (이제 run_data_prep은 이미 company_name이 설정된 상태의 state를 받음)
            socketio.emit('status_update', {'message': '데이터 준비 중...', 'progress': 10}, room=sid)
            time.sleep(1)
            updated_state_from_data_prep = run_data_prep(current_state)
            current_state.update(updated_state_from_data_prep)
            print("✅ [백엔드] 데이터 준비 완료")

            # 이전의 `if not current_state.get('company_name')` 체크는 이제 거의 불필요하지만,
            # 혹시 `run_data_prep` 내부에서 이름을 `None`으로 덮어쓸 경우를 대비한 최종 방어.
            if not current_state.get('company_name'):
                error_msg = f"'{ticker}' 기업의 기본 정보(회사명)를 분석 중 잃었습니다."
                print(f"🚨 {error_msg}")
                socketio.emit('status_update', {'message': error_msg, 'progress': -1}, room=sid)
                return 

            # 2. 해외 뉴스 분석 (이제 AnalysisState.company_name이 영문(선호) 이름으로 전달됨)
            # 뉴스 에이전트는 이 company_name을 사용하여 Supabase 벡터 검색을 수행해야 함.
            # 만약 Supabase 뉴스 데이터가 영문 이름으로 잘 인덱싱되어 있다면 이제 정상 작동해야 함.
            socketio.emit('status_update', {'message': '해외 뉴스 분석 중...', 'progress': 30}, room=sid)
            time.sleep(1)
            updated_state_from_news = run_news_analyst(current_state)
            current_state.update(updated_state_from_news)
            print("✅ [백엔드] 해외 뉴스 분석 완료")

            # 3. 국내 뉴스 분석 (동일)
            socketio.emit('status_update', {'message': '국내 뉴스 분석 중...', 'progress': 50}, room=sid)
            time.sleep(1)
            updated_state_from_domestic_news = run_domestic_news_analyst(current_state)
            current_state.update(updated_state_from_domestic_news)
            print("✅ [백엔드] 국내 뉴스 분석 완료")

            # 4. 시장 데이터 분석
            # run_market_correlation은 티커를 기반으로 시계열 데이터를 가져오므로,
            # 이 단계에서 "시계열 데이터를 가져오지 못했습니다" 오류는 해당 티커의 가격 데이터가 DB에 없는 것임.
            socketio.emit('status_update', {'message': '시장 데이터 분석 중...', 'progress': 70}, room=sid)
            time.sleep(1)
            updated_state_from_market_correlation = run_market_correlation(current_state)
            current_state.update(updated_state_from_market_correlation)
            print("✅ [백엔드] 시장 데이터 분석 완료")
            
            # 🚨 이전 수정: market_analysis_result가 None인 경우 빈 사전으로 초기화 (방어 로직 유지)
            if current_state.get('market_analysis_result') is None:
                current_state['market_analysis_result'] = {
                    "news_impact_data": [], 
                    "historical_prices": {}, 
                    "all_analyzed_tickers": [], 
                    "correlation_matrix": {} # 모든 필드를 빈 값으로 초기화
                }
                print("⚠️ market_analysis_result가 None이어서 빈 사전으로 초기화합니다. (시장 데이터 분석이 건너뛰어졌을 수 있음)")


            # 5. 최종 투자 브리핑 생성
            socketio.emit('status_update', {'message': '최종 투자 브리핑 생성 중...', 'progress': 90}, room=sid)
            time.sleep(1)
            updated_state_from_report_synthesizer = run_report_synthesizer(current_state)
            current_state.update(updated_state_from_report_synthesizer)
            print("✅ [백엔드] 최종 투자 브리핑 생성 완료")

            final_report = current_state.get("final_report")
            selected_news_for_frontend = current_state.get("selected_news", [])
            selected_domestic_news_for_frontend = current_state.get("selected_domestic_news", [])
            
            # 새롭게 추가된 데이터 필드를 추출
            historical_prices = current_state.get("historical_prices", {})
            news_event_markers = current_state.get("news_event_markers", {})
            all_analyzed_tickers = current_state.get("all_analyzed_tickers", [])
            
            # market_analysis_result에서 correlation_matrix 추출
            market_analysis_result = current_state.get("market_analysis_result", {})
            correlation_matrix = market_analysis_result.get("correlation_matrix", {})


            if final_report:
                socketio.emit('analysis_complete', {
                    'report': final_report,
                    'portfolio_summary': portfolio_summary,
                    'selected_news': selected_news_for_frontend,
                    'selected_domestic_news': selected_domestic_news_for_frontend,
                    'historical_prices': historical_prices,
                    'news_event_markers': news_event_markers,
                    'all_analyzed_tickers': all_analyzed_tickers,
                    'correlation_matrix': correlation_matrix,
                    'message': '분석 완료!'
                }, room=sid)
            else:
                socketio.emit('status_update', {'message': '오류: 최종 보고서 생성 실패.', 'progress': -1}, room=sid)

        except Exception as e:
            print(f"🚨 분석 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            socketio.emit('status_update', {'message': f"분석 중 오류 발생: {str(e)}", 'progress': -1}, room=sid)


if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0')