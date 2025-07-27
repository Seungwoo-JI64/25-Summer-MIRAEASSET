import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, current_app # current_app import 추가 (사용하지 않더라도 컨텍스트 문제 해결에 도움)
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
if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("경고: SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다. Supabase 연동 불가.")
else:
    from supabase import create_client, Client
    try:
        supabase_client_global: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized for app.py.")
    except Exception as e:
        print(f"🚨 Supabase 클라이언트 초기화 중 오류 발생: {e}")
        supabase_client_global = None


def _get_company_name_from_db(ticker: str) -> str:
    """
    Supabase에서 티커에 해당하는 회사 이름을 조회합니다.
    이 함수는 Flask 애플리케이션 컨텍스트에 독립적입니다.
    """
    if not supabase_client_global:
        return ticker # Supabase 연결 없으면 티커 반환

    company_name = ticker # 기본값은 티커
    try:
        if not (ticker.startswith('^') or ticker.endswith('=X')): # 일반 주식인 경우에만 테이블 조회
            # 미국 주식 이름 조회
            response_us = supabase_client_global.table("us_stocks").select("company_name").eq('ticker', ticker).limit(1).execute()
            if response_us.data and response_us.data[0].get('company_name'):
                company_name = response_us.data[0]['company_name']
            else: # 한국 주식 이름 조회
                response_kr = supabase_client_global.table("korean_stocks").select("company_name").eq('ticker', ticker).limit(1).execute()
                if response_kr.data and response_kr.data[0].get('company_name'):
                    company_name = response_kr.data[0]['company_name']
        else: # 지수/환율 처리 (이름 하드코딩)
            # 이 로직은 search_stocks와 get_single_stock_info에서도 중복되므로,
            # 별도의 딕셔너리로 관리하는 것이 더 깔끔할 수 있습니다.
            if ticker == '^GSPC':
                company_name = 'S&P 500 Index'
            elif ticker == '^KS11':
                company_name = 'KOSPI Composite Index'
            elif ticker == '^KQ11':
                company_name = 'KOSDAQ Composite Index'
            elif ticker == '^DJI':
                company_name = 'Dow Jones Industrial Average'
            elif ticker == '^IXIC':
                company_name = 'NASDAQ Composite Index'
            elif ticker == 'USDKRW=X':
                company_name = 'USD/KRW 환율'
            elif ticker == 'JPYKRW=X':
                company_name = 'JPY/KRW 환율'
            elif ticker == 'EURKRW=X':
                company_name = 'EUR/KRW 환율'
            # 추가적인 지수/환율은 여기에 추가

    except Exception as e:
        print(f"🚨 Supabase에서 회사 이름 조회 중 오류 발생: {e}")
    return company_name


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
        response = supabase_client_global.table(table_name).select("close_price").eq(ticker_filter_col, ticker).order(order_col, desc=True).limit(1).execute()
        
        data = response.data
        
        current_price = None
        if data and len(data) > 0 and 'close_price' in data[0]:
            current_price = data[0]['close_price']
            
        if current_price is None:
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
        name = stock_data.get('name', '알 수 없는 주식')

        # 각 주식의 상세 정보 및 손익 계산
        stock_summary = get_stock_price_and_info(ticker, purchase_price, quantity)
        stock_summary['name'] = name # 이름도 추가하여 반환
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
    
    # 헬퍼 함수를 사용하여 회사 이름 조회
    company_name = _get_company_name_from_db(ticker)
    stock_info['name'] = company_name
    
    return jsonify(stock_info)


# NEW: 주식 검색 엔드포인트
@app.route('/search_stocks', methods=['GET'])
def search_stocks():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify([])

    results = []
    MAX_SEARCH_RESULTS = 20 # 반환할 최대 검색 결과 수

    # 공통 지수/환율 이름 목록 (_get_company_name_from_db와 일관성 유지)
    common_indices_currencies = {
        '^GSPC': 'S&P 500 Index',
        '^IXIC': 'NASDAQ Composite',
        '^DJI': 'Dow Jones Industrial Average',
        '^KS11': 'KOSPI Composite Index',
        '^KQ11': 'KOSDAQ Composite Index',
        'USDKRW=X': 'USD/KRW 환율',
        'JPYKRW=X': 'JPY/KRW 환율',
        'EURKRW=X': 'EUR/KRW 환율',
    }

    try:
        unique_results = {} # 중복 방지를 위한 딕셔너리

        # 지수/환율 검색 먼저 (하드코딩된 이름 목록에서)
        for t, name in common_indices_currencies.items():
            if (query.lower() in t.lower() or query.lower() in name.lower()):
                unique_results[t] = {'ticker': t, 'name': name}

        # Supabase에 연결되어 있을 경우에만 주식 테이블 검색
        if supabase_client_global:
            # 미국 주식 검색 (티커 또는 이름)
            response_us_ticker = supabase_client_global.table("us_stocks").select("ticker, company_name").ilike('ticker', f'%{query}%').limit(MAX_SEARCH_RESULTS).execute()
            response_us_name = supabase_client_global.table("us_stocks").select("ticker, company_name").ilike('company_name', f'%{query}%').limit(MAX_SEARCH_RESULTS).execute()
            
            for r in response_us_ticker.data:
                if r.get('ticker'):
                    unique_results[r['ticker']] = {'ticker': r['ticker'], 'name': r.get('company_name', r['ticker'])}
            for r in response_us_name.data:
                if r.get('ticker'):
                    unique_results[r['ticker']] = {'ticker': r['ticker'], 'name': r.get('company_name', r['ticker'])}
            
            # 한국 주식 검색 (티커 또는 이름)
            if len(unique_results) < MAX_SEARCH_RESULTS: # 아직 MAX_SEARCH_RESULTS에 도달하지 않았다면
                response_kr_ticker = supabase_client_global.table("korean_stocks").select("ticker, company_name").ilike('ticker', f'%{query}%').limit(MAX_SEARCH_RESULTS - len(unique_results)).execute()
                response_kr_name = supabase_client_global.table("korean_stocks").select("ticker, company_name").ilike('company_name', f'%{query}%').limit(MAX_SEARCH_RESULTS - len(unique_results)).execute()

                for r in response_kr_ticker.data:
                    if r.get('ticker'):
                        unique_results[r['ticker']] = {'ticker': r['ticker'], 'name': r.get('company_name', r['ticker'])}
                for r in response_kr_name.data:
                    if r.get('ticker'):
                        unique_results[r['ticker']] = {'ticker': r['ticker'], 'name': r.get('company_name', r['ticker'])}
                
        # unique_results 딕셔너리의 값을 리스트로 변환
        results = list(unique_results.values())

        # 최종 결과 제한 및 이름으로 정렬
        final_results = sorted(results, key=lambda x: x['name'])[:MAX_SEARCH_RESULTS]

        return jsonify(final_results)

    except Exception as e:
        print(f"🚨 주식 검색 중 오류 발생: {e}")
        return jsonify({"error": str(e)}), 500


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
        threading.Thread(target=run_full_analysis_pipeline, args=(ticker, request.sid)).start()


def run_full_analysis_pipeline(ticker: str, sid: str):
    """
    전체 분석 파이프라인을 실행하고 진행 상황을 클라이언트에 emit합니다.
    """
    # 백그라운드 스레드에서 Flask 컨텍스트 사용을 위해 push
    # 이렇게 해야 get_stock_price_and_info 등이 정상 작동
    # 그러나 get_single_stock_info는 이제 _get_company_name_from_db를 호출하므로 컨텍스트 불필요
    # with app.app_context(): # 이미 handle_start_analysis_request에서 컨텍스트 안에서 스레드 시작했으므로 필요 없을 수 있음.
                            # 하지만 안전을 위해 run_full_analysis_pipeline 내부에서 다시 컨텍스트를 push하는 것도 가능.
                            # 여기서는 get_stock_price_and_info 호출 때문에 컨텍스트가 필요함.
    
    # get_stock_price_and_info가 컨텍스트를 필요로 할 수 있으므로, 컨텍스트를 명시적으로 push합니다.
    with app.app_context():
        initial_state: AnalysisState = {
            "ticker": ticker,
            "company_name": None,
            "company_description": None,
            "financial_health": None,
            "selected_news": None,
            "selected_domestic_news": None,
            "market_analysis_result": None,
            "final_report": None,
            # 에이전트가 상태에 추가할 데이터를 위한 필드 (market_correlation_agent에서 채워질 예정)
            "historical_prices": None,
            "news_event_markers": None,
            "all_analyzed_tickers": None,
            # 기존 필드 (분석 모델 내부에서만 사용)
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
            portfolio_summary = get_stock_price_and_info( # 이 함수는 컨텍스트가 필요할 수 있음
                ticker,
                selected_stock_portfolio_info.get('purchase_price', 0),
                selected_stock_portfolio_info.get('quantity', 0)
            )
            portfolio_summary['name'] = selected_stock_portfolio_info.get('name') # 이름 추가
        else:
            # 포트폴리오에 없는 주식인 경우, 이름 조회 시도
            # 뷰 함수 get_single_stock_info 대신 헬퍼 함수를 직접 호출
            company_name_for_summary = _get_company_name_from_db(ticker)
            portfolio_summary = {
                "ticker": ticker,
                "message": "선택된 주식의 포트폴리오 정보(구매가, 수량)를 찾을 수 없습니다.",
                "name": company_name_for_summary # 조회된 이름 사용
            }
            print(portfolio_summary['message'])


        try:
            socketio.emit('status_update', {'message': '데이터 준비 중...', 'progress': 10}, room=sid)
            time.sleep(1) # 테스트를 위한 지연
            current_state.update(run_data_prep(current_state))
            print("✅ [백엔드] 데이터 준비 완료")

            socketio.emit('status_update', {'message': '해외 뉴스 분석 중...', 'progress': 30}, room=sid)
            time.sleep(1) # 테스트를 위한 지연
            current_state.update(run_news_analyst(current_state))
            print("✅ [백엔드] 해외 뉴스 분석 완료")

            socketio.emit('status_update', {'message': '국내 뉴스 분석 중...', 'progress': 50}, room=sid)
            time.sleep(1) # 테스트를 위한 지연
            current_state.update(run_domestic_news_analyst(current_state))
            print("✅ [백엔드] 국내 뉴스 분석 완료")

            socketio.emit('status_update', {'message': '시장 데이터 분석 중...', 'progress': 70}, room=sid)
            time.sleep(1) # 테스트를 위한 지연
            current_state.update(run_market_correlation(current_state))
            print("✅ [백엔드] 시장 데이터 분석 완료")

            socketio.emit('status_update', {'message': '최종 투자 브리핑 생성 중...', 'progress': 90}, room=sid)
            time.sleep(1) # 테스트를 위한 지연
            current_state.update(run_report_synthesizer(current_state))
            print("✅ [백엔드] 최종 투자 브리핑 생성 완료")

            final_report = current_state.get("final_report")
            selected_news_for_frontend = current_state.get("selected_news", [])
            selected_domestic_news_for_frontend = current_state.get("selected_domestic_news", [])
            
            # 새롭게 추가된 데이터 필드를 추출
            historical_prices = current_state.get("historical_prices", {})
            news_event_markers = current_state.get("news_event_markers", {})
            all_analyzed_tickers = current_state.get("all_analyzed_tickers", [])
            
            # market_analysis_result에서 correlation_matrix 추출 (이제 사용되지 않지만, 데이터 구조 일관성을 위해 유지)
            market_analysis_result = current_state.get("market_analysis_result", {})
            correlation_matrix = market_analysis_result.get("correlation_matrix", {})


            if final_report:
                socketio.emit('analysis_complete', {
                    'report': final_report,
                    'portfolio_summary': portfolio_summary, # 포트폴리오 정보가 없는 주식도 여기에는 이름 정보가 들어있음
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
