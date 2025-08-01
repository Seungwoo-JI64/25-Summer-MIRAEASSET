# 25-Summer-MIRAEASSET
2025년 여름방학 B.a.f 미래에셋공모전 서비스부분 DATA TADA팀  
**서정유**, **유희준**, **지승우**  
대표 연락처 : swoo64@naver.com  

# 1. 서비스 접속 링크
https://datatada-miraeasset-webservice.azurewebsites.net/  
본 서비스는 프로토타입으로서, 2025년 8월 22일 자정까지 시범 운영됩니다.  

# 2. 프로젝트 설명
## 2.1 서비스 개요
## 2.2 구동 방식
<img alt="Image" width="1920" height="790" src="https://private-user-images.githubusercontent.com/180622587/473487790-b6b42985-a95f-4c39-8736-2e38c4bf6503.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NTQwNTgxMTMsIm5iZiI6MTc1NDA1NzgxMywicGF0aCI6Ii8xODA2MjI1ODcvNDczNDg3NzkwLWI2YjQyOTg1LWE5NWYtNGMzOS04NzM2LTJlMzhjNGJmNjUwMy5wbmc_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUwODAxJTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MDgwMVQxNDE2NTNaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT00ZDliMWQyNzI4MzI1OGI4OGEzN2M5ZWZiZDI0OWI4MDU3MGQ4MzM5YjkzNjk1ZjRmOWMxNDk4Mzk4ZmY4ZjQ4JlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9.2rTPSMa0w2w7LBHDmbz4it3OHr2rcv60uAA_P3SARN8">  


# 3. Github 저장 파일 설명
| 25-Summer-MIRAEASSET/.github/workflows |  |  
|---|---|  
| `daily_financial_indices.yml` | 깃허브 Actions `증권데이터/지표지수업로드_매일_jsw.py` 자동화 |  
| `ko_daily_stock_data.yml` | 깃허브 Actions `주식데이터/한국_주식추출_매일_jsw.py` 자동화 |  
| `us_daily_stock_data.yml` | 깃허브 Actions `주식데이터/미국_주식추출_매일_jsw.py` 자동화 |  
   
| 25-Summer-MIRAEASSET/주식데이터 |  |
|---|---|
| `한국_주식추출_매일_jsw.py` | yfinance API, 깃허브 Actions를 이용하여 매일 UTC+9 06시 주식 추출 자동화 |  
| `미국_주식추출_매일_jsw.py` | yfinance API, 깃허브 Actions를 이용하여 매일 UTC+9 06시 주식 추출 자동화 |  
| `주식추출_2년전_jsw.ipynb` | yfinance API를 이용하여 한국, 미국 시총 100 기업 2년치 주식 수집 (23.07.31~25.07.31) |  
| `주식크롤링_yhj.ipynb` | 야후 금융 한국, 미국 시총 100 기업명 웹크롤링 추출 |  
| `기업설명추가_jsw.ipynb` | yfinance API를 이용하여 한국, 미국 시총 100 기업의 설명문 추출 |  
| `기업설명_한글번역_jsw.ipynb` | `HyperCLOVA X`를 이용하여 기업 설명문 한국어 번역 |  

| 25-Summer-MIRAEASSET/증권데이터 |  |
|---|---|
| `2년치지표DB업로드_jsw.ipynb` | yfinance API를 이용하여 한국, 미국 주요 증시지표 2년치 수집 (23.07.01~25.07.11) |  
| `지표지수업로드_매일_jsw.py` | yfinance API, 깃허브 Actions을 활용하여 매일 UTC+9 06시 지표 추출 자동화 |  

| 25-Summer-MIRAEASSET/ko_news_scraping |  |
|---|---|  
| `최종_국내뉴스요약_jsw.py` | `Render`를 이용하여 매일 UTC+9 08시 연합뉴스 금융 뉴스 수집, 요약 및 임베딩 자동화 |
| `Dockerfile` | `Render` 최종_국내뉴스요약_jsw.py 실행환경 이미지 생성 |
| `requirements.txt` | `Render` 최종_국내뉴스요약_jsw.py 라이브러리 설치 |

| 25-Summer-MIRAEASSET/miraeasset_web_app | |
|---|---|
| `app.py` | Flask와 Socket.IO를 기반으로, 사용자의 분석 요청을 받아 AI 에이전트 파이프라인을 총괄하고 프론트엔드와 실시간으로 통신하는 메인 서버 파일 |
| `Dockerfile` | 표준화된 컨테이너 이미지를 생성 |
| `portfolio.json` | 사용자의 보유 주식 포트폴리오(예시, 임의생성) |
| `requirements.txt` | 서비스가 구동하기 위한 모든 파이썬 라이브러리 지정 |
| 25-Summer-MIRAEASSET/miraeasset_web_app/analysis_model |  |
| `state.py` | AI 분석 파이프라인의 각 단계를 거치면서 기업 정보, 뉴스, 시장 데이터 등 모든 분석 결과가 누적되는 중앙 데이터 전달 객체 정의 |
| 25-Summer-MIRAEASSET/miraeasset_web_app/analysis_model/agents |  |
| `data_prep_agent.py` | 사용자가 요청한 기업의 기본 정보와 재무 건전성 요약을 데이터베이스에서 가져와 분석의 기초를 마련하는 에이전트 |
| `domestic_news_analyst_agent.py` | 국내 뉴스를 대상으로, RAG(벡터 검색) 기술로 관련 기사를 찾고 `Gemini AI`를 이용해 가장 영향력 있는 뉴스를 선별 및 분석하는 에이전트 |
| `market_correlation_agent.py` | 뉴스 분석으로 도출된 모든 관련 주체들의 과거 주가 데이터를 DB에서 가져와 ~~통계적 상관관계를 계산하고,~~ 그래프 시각화를 위한 데이터를 가공하는 에이전트 |
| `news_analyst_agent.py` | 해외 뉴스를 대상으로, RAG(벡터 검색) 기술로 관련 기사를 찾고 `Gemini AI`를 이용해 가장 영향력 있는 뉴스를 선별 및 분석하는 에이전트 |
| `report_synthesizer_agent.py` | 모든 분석 데이터를 종합하여, HyperCLOVA X를 호출함으로써 요약, 심층 분석, 투자 전략이 포함된 최종 투자 브리핑을 생성하는 에이전트 |
| 25-Summer-MIRAEASSET/miraeasset_web_app/templates |  |
| `index.html` | 사용자가 보는 웹 화면(UI)으로, Socket.IO로 서버와 통신하며 분석 과정을 보여주고 Chart.js를 이용해 최종 보고서와 동적 그래프를 시각화 |

| 25-Summer-MIRAEASSET/news_scraping | |
|---|---|
| `최종_영문뉴스요약_jsw.py` | Render를 이용하여 매일 UTC+9 08시, 20시 야후 금융 뉴스 주십, 요약 및 임베딩 자동화 |
| `Dockerfile` | Render 최종_영문뉴스요약_jsw.py 실행환경 이미지 생성 |
| `requirements.txt` | Render 최종_영문뉴스요약_jsw.py 라이브러리 설치 |

| 25-Summer-MIRAEASSET | |  
|---|---|
| `requirements.txt` | 깃허브 Actions 구동에 필요한 라이브러리 설치 목록 |

# 4. 데이터베이스 테이블 목록 
Supabase DBMS를 통해 관리한다.

### company_summary
yfinance API에서 회사 설명 추출  

| 피쳐명 | 설명 | 형식 |    
|---|---|---|  
| `ticker` | 기업 식별 기호 | text |   
| `company_name` | 기업명 | text |  
| `summary` | 기업 설명문 | text |  
| `summary_embedding` | 기업 설명문 임베딩 | vector(768) |  
| `ko_summary` | 기업 설명문(한국어 번역) | text |  


### financial_indices
yfinance API에서 주요 지표 지수 추출  

| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| `id` | 자료 저장 순서 | int8 |  
| `index_en` | 지표 식별 기호 (ticker) | text |  
| `index_ko` | 지표명(한국어) | text |  
| `date` | 날짜 | timestamptz |
| `value` | 지수 | numeric |
| `created_at` | 추출시간 | timestamptz |  


### financial_news_summary
야후 금융 뉴스 추출 요약 및 임베딩  

| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| `id` | 자료 저장 순서 | int8 |  
| `title` | 뉴스 제목 | text |  
| `publich_date` | 뉴스 발간 일자 | timestamptz |  
| `url` | 뉴스 링크 | text |
| `summary` | 뉴스 요약 | text |
| `embedding` | 뉴스 요약 임베딩 | vector(768) |
| `created_at` | 추출시간 | timestamptz |

### financial_statements
KOPIS 100 기업 재무제표와 건전성 보고서  

| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| `ticker` | 기업 식별 기호 | text |  
| `company_name` | 기업명 | text |  
| `prompt` | LLM에 입력할 프롬프트(재무제표 포함) | timestamptz |  
| `summary` | 기업 건전성 보고서 | text |

### indices_summary
yfinance API에서 주요 지표 설명 추출  

| 피쳐명 | 설명 | 형식 |    
|---|---|---|  
| `ticker` | 지표 식별 기호 | text |   
| `index_name` | 기업명 | text |  
| `ko_summary` | 기업 설명문(한국어 번역) | text |  

### ko_financial_news_summary
연합뉴스 금융 뉴스 추출 요약 및 임베딩  

| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| `id` | 자료 저장 순서 | int8 |  
| `title` | 뉴스 제목 | text |  
| `publich_date` | 뉴스 발간 일자 | timestamptz |  
| `url` | 뉴스 링크 | text |
| `summary` | 뉴스 요약 | text |
| `embedding` | 뉴스 요약 임베딩 | vector(768) |
| `created_at` | 추출시간 | timestamptz |

### korean_stocks
yfinance API 한국 시총 100 주가 추출  

| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| `time` | 날짜 | timestamptz |  
| `ticker` | 기업 식별 기호 | text |  
| `company_name` | 기업명 | text |  
| `close_price` | 종가 | numeric |
| `volume` | 거래량 | int8 |
| `created_at` | 추출시간 | timestamptz |

### un_stocks
yfinance API 미국 시총 100 주가 추출  

| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| `time` | 날짜 | timestamptz |  
| `ticker` | 기업 식별 기호 | text |  
| `company_name` | 기업명 | text |  
| `close_price` | 종가 | numeric |
| `volume` | 거래량 | int8 |
| `created_at` | 추출시간 | timestamptz |
