import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import sys
import threading
import time
from typing import Optional, List, Dict, Any # Optional import 추가

# 프로젝트 루트를 Python Path에 추가하여 analysis_model을 모듈로 임포트할 수 있게 합니다.
# 이 줄은 app.py가 miraeasset_web_app/analysis_model/analysis_model 경로를 찾도록 돕습니다.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# .env 파일 로드 (가장 먼저 실행)
load_dotenv()

# analysis_model의 핵심 로직을 임포트합니다.
from analysis_model.state import AnalysisState, MarketAnalysisResult # MarketAnalysisResult도 임포트
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

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("경고: SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다. Supabase 연동 불가.")
    supabase_client_global = None
else:
    from supabase import create_client, Client
    supabase_client_global: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client initialized for app.py.")


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
        # 변경: korean_stocks/us_stocks 테이블에서 'time' 컬럼을 사용하도록 수정
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

# --- 새 기능: 개별 주식 정보 조회 엔드포인트 ---
@app.route('/stock_info/<ticker>', methods=['GET'])
def get_single_stock_info(ticker: str):
    """
    특정 티커의 현재 주가 정보만 반환합니다. (포트폴리오 정보 없이)
    """
    # purchase_price와 quantity를 None으로 전달하여 손익 계산을 건너뜜
    stock_info = get_stock_price_and_info(ticker, purchase_price=None, quantity=None)
    
    # Supabase에서 회사 이름도 조회 (있다면)
    company_name = ticker # 기본값
    try:
        # 이 함수는 주식 티커에 대해서만 이름 조회를 시도하며, 지수/환율은 건너뜜
        if not (ticker.startswith('^') or ticker.endswith('=X')):
            # 미국 주식 정보 테이블에 회사 이름이 있는지 먼저 검색
            response_us = supabase_client_global.table("us_stocks_info").select("company_name").eq('ticker', ticker).limit(1).execute()
            if response_us.data:
                company_name = response_us.data[0].get('company_name', ticker)
            else: # 한국 주식 정보 테이블에 회사 이름이 있는지 검색
                response_kr = supabase_client_global.table("korean_stocks_info").select("company_name").eq('ticker', ticker).limit(1).execute()
                if response_kr.data:
                    company_name = response_kr.data[0].get('company_name', ticker)
    except Exception as e:
        print(f"🚨 회사 이름 조회 중 오류 발생: {e}")

    stock_info['name'] = company_name
    return jsonify(stock_info)


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
    
    threading.Thread(target=run_full_analysis_pipeline, args=(ticker, request.sid)).start()

def run_full_analysis_pipeline(ticker: str, sid: str):
    """
    전체 분석 파이프라인을 실행하고 진행 상황을 클라이언트에 emit합니다.
    """
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
        portfolio_summary = get_stock_price_and_info(
            ticker,
            selected_stock_portfolio_info.get('purchase_price', 0),
            selected_stock_portfolio_info.get('quantity', 0)
        )
        portfolio_summary['name'] = selected_stock_portfolio_info.get('name') # 이름 추가
    else:
        portfolio_summary = {
            "ticker": ticker,
            "message": "선택된 주식의 포트폴리오 정보(구매가, 수량)를 찾을 수 없습니다.",
            "name": ticker # 이름을 찾을 수 없으면 티커로 표시
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
        
        # market_analysis_result에서 correlation_matrix 추출
        market_analysis_result = current_state.get("market_analysis_result", {})
        correlation_matrix = market_analysis_result.get("correlation_matrix", {})


        if final_report:
            socketio.emit('analysis_complete', {
                'report': final_report,
                'portfolio_summary': portfolio_summary,
                'selected_news': selected_news_for_frontend,
                'selected_domestic_news': selected_domestic_news_for_frontend,
                'historical_prices': historical_prices,             # 추가
                'news_event_markers': news_event_markers,         # 추가
                'all_analyzed_tickers': all_analyzed_tickers,     # 추가
                'correlation_matrix': correlation_matrix,         # 추가
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
    # Docker 환경은 프로덕션으로 간주될 수 있으므로 debug=False로 설정하고
    # Eventlet/Gevent와 같은 WSGI 서버를 사용해야 하지만,
    # 여기서는 테스트를 위해 allow_unsafe_werkzeug=True를 추가합니다.
    # 실제 프로덕션에서는 Gunicorn과 같은 WSGI 서버를 Dockerfile의 CMD에서 사용해야 합니다.
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0') # host='0.0.0.0'을 추가합니다.
