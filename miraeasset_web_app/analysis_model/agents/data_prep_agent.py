# 1. 데이터 준비 에이전트

import sys
import os
from typing import Dict, Any
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from analysis_model.state import AnalysisState
from supabase import create_client, Client

#######################################################
# 데이터베이스 환경설정
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("Supabase URL과 Key를 환경 변수로 설정해야 합니다.")

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# #######################################################
# # 데이터베이스 - 기업 설명문 조회
# ## 더이상 사용하지 않음
# def load_company_info_from_supabase(company_name: str) -> Dict[str, Any]:
#     """
#     Supabase 'company_summary' 테이블에서 기업의 티커와 기업설명문(영문)을 조회하는 함수.
#     더이상 사용하지 않음
#     """
#     print(f"[Data Prep] 'company_summary' 테이블에서 '{company_name}'의 티커, 기업설명문(영문)을 조회합니다.")
#     try:
#         # 데이터베이스 데이터 가져오기
#         query_result = supabase_client \
#             .table("company_summary") \
#             .select("ticker, summary") \
#             .eq("company_name", company_name) \
#             .single() \
#             .execute()

#         # 데이터 추출
#         if query_result.data:
#             return {
#                 "ticker": query_result.data.get('ticker'),
#                 "company_description": query_result.data.get('summary')
#             }
#         else:
#             return {
#                 "ticker": None,
#                 "company_description": "해당 기업의 개요 정보가 DB에 존재하지 않습니다."
#             }
#     except Exception as e:
#         print(f"Supabase 'company_summary' 조회 중 에러 발생: {e}")
#         return {
#             "ticker": None,
#             "company_description": "데이터베이스 조회 중 오류가 발생했습니다."
#         }

# #######################################################
# # 데이터베이스 - 기업건전성 보고서 조회
# ## 더이상 사용하지 않음
# def load_financial_statements_from_supabase(ticker: str) -> str:
#     """
#     Supabase 'financial_statements' 테이블에서 티커로 재무 건전성 텍스트를 조회하는 함수.
#     더이상 사용하지 않음
#     """
#     print(f"[Data Prep] 'financial_statements' 테이블에서 티커 '{ticker}'로 재무 분석 데이터를 조회합니다.")
#     try:
#         # 데이터베이스 데이터 가져오기
#         query_result = supabase_client \
#             .table("financial_statements") \
#             .select("ticker, summary") \
#             .eq("ticker", ticker) \
#             .single() \
#             .execute()

#         # 데이터 추출
#         if query_result.data:
#             return {
#                 "ticker": query_result.data.get('ticker'),
#                 "financial_statements": query_result.data.get('summary')
#             }
#         else:
#             return {
#                 "ticker": None,
#                 "financial_statements": "해당 기업의 재무제표 정보가 DB에 존재하지 않습니다."
#             }
#     except Exception as e:
#         print(f"Supabase 'financial_statements' 조회 중 에러 발생: {e}")
#         return {
#             "ticker": None,
#             "financial_statements": "데이터베이스 조회 중 오류가 발생했습니다."
#         }



#######################################################
# 데이터 준비 에이전트 실행 함수
# 기업 설명문과 건전성 보고서를 불러온다

def run_data_prep(state: AnalysisState) -> Dict[str, Any]:
    ticker = state.get("ticker")
    company_name = state.get("company_name")

    if not ticker:
        raise ValueError("상태(State)에 'ticker'가 없습니다. 티커를 반드시 제공해야 합니다.")

    company_description = None
    ko_company_description = None # 기업 설명문 한국어 번역본을 추가로 가져오기
    financial_statements = None

    #######################################################
    # 기업 설명문 영문 + 한국어 번역본 추가 조회
    ## 위에서 정의한 함수 대체
    try:
        res = supabase_client.table("company_summary").select("company_name, summary, ko_summary").eq("ticker", ticker).single().execute()
        if res.data:
            company_name = res.data.get("company_name")
            company_description = res.data.get("summary")
            ko_company_description = res.data.get("ko_summary")  # 국문 설명 조회
        else:
            company_name = None
            company_description = "DB에 해당 기업 정보가 없습니다."
            ko_company_description = "DB에 해당 기업 정보가 없습니다, 데이터 준비 에이전트 오류."
    except Exception as e:
        company_name = None
        company_description = f"DB 조회 오류: {e}"
        ko_company_description = f"DB 조회 오류: {e}"

    #######################################################
    # 기업건전성 보고서 조회
    ## 위에서 정의한 함수 대체
    try:
        financial_res = supabase_client.table("financial_statements").select("summary").eq("ticker", ticker).single().execute()
        if financial_res.data:
            financial_statements = financial_res.data.get("summary")
        else:
            financial_statements = "DB에 재무제표 데이터가 없습니다."
    except Exception as e:
        financial_statements = f"DB 조회 오류: {e}"

    return {
        "company_name": company_name,
        "ticker": ticker,
        "company_description": company_description,
        "ko_company_description": ko_company_description,  # 국문 설명 추가
        "financial_health": financial_statements
    }

