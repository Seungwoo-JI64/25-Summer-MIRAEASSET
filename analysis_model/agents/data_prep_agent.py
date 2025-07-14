#####################################
# 데이터 준비 에이전트

# Supabase 데이터베이스에서 기업의 재무 건전성 분석 결과를 조회하는 에이전트
# 기업의 이름은 state에서 받아온다.
# 즉 기업 이름은 LangGraph의 파이프라인 시작 시 제공되어야 한다.

import os
import time
from typing import Dict, Any
from supabase import create_client, Client

# 상위 폴더에 있는 state.py 모듈에서 AnalysisState 클래스를 가져옵니다.
from ..state import AnalysisState

# --- Supabase 클라이언트 설정 ---
# 루트폴더의 .env 파일에 저장한 Supabase 접속 정보를 불러온다.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Supabase URL과 Key가 설정되지 않았다면 에러를 발생시켜 실행을 중단합니다.
if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("Supabase URL과 Key를 환경 변수로 설정해야 합니다.")

# Supabase와 통신
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Supabase 정보 조회 함수
## 1. 기업 티커와 개요
def load_company_info_from_supabase(company_name: str) -> Dict[str, Any]:
    """
    Supabase 'company_summary' 테이블에서 기업의 티커와 개요를 조회하는 함수.

    입력:
        company_name (str): 조회할 기업의 이름.
    출력:
        Dict[str, Any]: 티커와 기업 개요가 담긴 딕셔너리.
    """
    print(f"[Data Prep] 'company_summary' 테이블에서 '{company_name}'의 티커, 개요를 조회합니다.")
    try:
        # 'company_summary' 테이블에서 'ticker'와 'summary' 컬럼을 조회합니다.
        query_result = supabase_client.table("company_summary").select("ticker, summary").eq("company_name", company_name).single().execute()

        if query_result.data:
            return {
                "ticker": query_result.data.get('ticker'),
                "company_description": query_result.data.get('summary')
            }
        else:
            # 만약 데이터가 없다면
            return {
                "ticker": None,
                "company_description": "해당 기업의 개요 정보가 DB에 존재하지 않습니다."
            }
    except Exception as e:
        print(f"Supabase 'company_summary' 조회 중 에러 발생: {e}")
        return {
            "ticker": None,
            "company_description": "데이터베이스 조회 중 오류가 발생했습니다."
        }

## 2. 기업의 재무 건정성
def load_financial_health_from_supabase(company_name: str) -> str: #str타입으로 반환한다
    """
    Supabase DB에서 기업의 재무 건전성 분석 결과를 조회하는 함수.
    
    입력:
        company_name (str): 조회할 기업의 이름. run_data_prep 함수에서 전달받는다
    출력:
        str: Supabase DB에서 조회한 재무 건전성 텍스트.
    """
    print(f"[Data Prep] '**********재무건정성테이블명***********' 테이블에서 '{company_name}'의 재무 분석 데이터를 조회합니다.")
    try:
        # supabase_client.table("테이블명")으로 특정 테이블에 접근합니다.
        # .select("컬럼명")으로 원하는 데이터를 지정하고,
        # .eq("컬럼명", "값")으로 'company_name' 컬럼이 입력값과 일치하는 행을 찾습니다.
        # .execute()로 쿼리를 실행합니다.
        query_result = supabase_client.table("**********재무건정성테이블명***********").select("financial_health").eq("company_name", company_name).execute()

        # 쿼리 결과(query_result.data)에 데이터가 있는지 확인합니다.
        if query_result.data:
            # 첫 번째 결과의 'financial_health' 필드 값을 반환합니다.
            return query_result.data[0]['financial_health']
        else:
            return "해당 기업의 재무 분석 데이터가 DB에 존재하지 않습니다."

    except Exception as e:
        print(f"Supabase 조회 중 에러 발생: {e}")
        return "데이터베이스 조회 중 오류가 발생했습니다."
    
## 3. 데이터 준비 
def run_data_prep(state: AnalysisState) -> Dict[str, Any]:
    """
    데이터 준비 에이전트의 실행 함수.

    입력:
        state (AnalysisState): state.py의 AnalysisState 객체에서 'company_name'을 읽어 작업을 수행합니다.

    출력:
        Dict[str, Any]: 조회된 모든 기초 정보(티커, 기업개요, 재무건전성)를 담은 딕셔너리.
                        LangGraph는 이 결과를 기존 state에 자동으로 병합해줍니다.
    """
    print("\n--- [Data Prep] 데이터 준비 에이전트 실행 ---")
    company_name = state.get("company_name")

    if not company_name:
        raise ValueError("상태(State)에 'company_name'이 없습니다. 파이프라인 시작 시 반드시 제공되어야 합니다.")

    # 각 테이블에서 필요한 정보를 조회합니다.
    company_info = load_company_info_from_supabase(company_name)
    financial_health_text = load_financial_health_from_supabase(company_name)

    # 분석된 결과를 상태(State)에 추가하여 반환
    return {
        "ticker": company_info.get("ticker"),
        "company_description": company_info.get("company_description"),
        "financial_health": financial_health_text
    }
