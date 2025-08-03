# 25-Summer-MIRAEASSET
2025년 여름방학 B.a.f 미래에셋공모전 서비스부분 DATA TADA팀  
**서정유**, **유희준**, **지승우**  
대표 연락처 : swoo64@naver.com  

# 1. 서비스 접속 링크
https://datatada-miraeasset-webservice.azurewebsites.net/  
본 서비스는 프로토타입으로서, 2025년 8월 22일 자정까지 시범 운영됩니다.  

# 2. 프로젝트 설명
## 2.1 서비스 개요

 &nbsp;본 서비스는 개인 투자자들이 방대한 금융 데이터와 뉴스를 효과적으로 분석하고, 신뢰할 수 있는 정보에 기반하여 합리적인 투자 결정을 내릴 수 있도록 지원하는 **AI 기반 투자 브리핑 자동 생성 서비스**입니다.  
 &nbsp;기존의 많은 AI 금융 서비스들이 결과만을 제시하는 **블랙박스(Black Box)** 형태로 운영되어 사용자의 신뢰를 얻기 어렵다는 한계에 주목했습니다. 이러한 문제를 해결하기 위해, AI의 분석 과정을 투명하게 공개하는 **유리상자(Glass Box)** 모델을 핵심 목표로 삼습니다. AI가 어떤 데이터를 참고하고 어떤 과정을 거쳐 결론을 도출했는지 명확히 제시함으로써, 사용자가 AI의 분석을 비판적으로 수용하고 최종적인 투자 판단의 주체로 설 수 있도록 돕습니다.  
 &nbsp;이를 구현하기 위해 서비스는 `LangChain`의 설계 사상을 차용한 자율 에이전트 시스템으로 구축되었습니다. 사용자의 요청이 들어오면, **데이터 준비 → 뉴스 분석(RAG) → 시장 데이터 분석 → 최종 보고서 생성**의 각 단계를 전문화된 **AI 에이전트**들이 순차적으로 수행합니다. 이 과정에서 `Gemini`는 `RAG` 기반의 뉴스 분석을, `HyperCLOVA X`는 최종 보고서의 종합적인 작성을 담당하며, 모든 데이터는 `Supabase` 데이터베이스를 중심으로 관리됩니다. 사용자는 웹 인터페이스를 통해 분석을 요청하고, 실시간으로 업데이트되는 분석 과정을 지켜본 후, 최종적으로 텍스트 보고서와 `Chart.js`로 시각화된 동적 데이터(주가, 뉴스 발생 시점 등)를 함께 제공받습니다. 이렇게 완성된 서비스는 `Docker 컨테이너 기술`을 통해 패키징되어, `Azure 클라우드 플랫폼`에서 안정적으로 운영됩니다.

## 2.2 파이프라인 구동 방식
<img alt="Image" width="1920" height="790" src="https://private-user-images.githubusercontent.com/180622587/473487790-b6b42985-a95f-4c39-8736-2e38c4bf6503.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NTQxNDE4NjUsIm5iZiI6MTc1NDE0MTU2NSwicGF0aCI6Ii8xODA2MjI1ODcvNDczNDg3NzkwLWI2YjQyOTg1LWE5NWYtNGMzOS04NzM2LTJlMzhjNGJmNjUwMy5wbmc_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUwODAyJTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MDgwMlQxMzMyNDVaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT00Zjg2OWRlNTU4ZjJmMzdiZTBmNzE3YzI0Nzc3NzdiYTJlYjllZDhmOGY4ZDVkOTY2OTVlNjg4MDQ2MzNlNTE5JlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9.wVmQf0ztf2Y3qicWXFyTBjlE7yK9lfDhlAtUghGg8mM">

### 2.2.1 데이터 수집, 텍스트 전처리

#### ① `기업 재무제표 및 건전성 보고서`
 &nbsp;**재무제표**에 기반하여 **기업의 건전성**을 파악하는 것은 투자를 하기 전 선행되어야 하는 주된 과제이다. 개인이 해당 과정을 진행하는 것은 상당히 번거로운 일이므로 미리 이를 생성한다면 큰 도움이 된다. 또한 `최종 분석 보고서`의 근거자료에도 이것이 활용되기 때문에 그 중요도는 높다. **DART공시 API**에서 제공하는 재무제표 데이터를 수집하였으며, **KOSPI 100**에 해당하는 기업들이 해당되며, 2023년~2025년 1분기 각 기업의 매출액, 당기순이익, 영업이익 등이 포함된다. 이를 기반으로 건전성 보고서를 생성한다. 여기엔 기업의 유동성, 수익성, 안전성의 분석 결과가 나타나며 투자 시 주의점과 리스크 요인도 보여준다. 건전성 보고서는 **HyperCLOVA X**를 통해 작성하였다. 재무제표 데이터와 그에 맞는 프롬프트를 작성하여 **CLOVA X**에 전달하였고, 그 예시는 아래와 같다. 부채 수준, 현금흐름, 자산 활용 등 다양한 요소를 종합적으로 고려하기 때문에 기업의 재무 상태가 튼튼하고 안전한지 알 수 있다.

#### ② `금융 뉴스 및 요약, 텍스트 임베딩`
 &nbsp;본 프로젝트는 금융 뉴스를 기반으로 해당 기업의 주가 변동을 분석하는것이 주된 골자이다. 따라서 **연합뉴스**와 **Yahoo Finance**에서 금융 뉴스들을 매일 수집하였다. 수집된 자료는 뉴스 제목, 출간 일자, 링크, 뉴스 본문이며, **Gemini AI**를 통해 이를 요약을 진행하였다. 또한 Gemini API에서 제공하는 **Embedding**을 활용해 요약문으로 **768차원**으로 벡터화하였다. 이것은 **RAG기반 유사도 검색**을 위한 필수 요건이며, AI의 구동에 있어 훨씬 경제적이고 빠른 방법이다.

#### ③ `기업 • 지표 주가`
 &nbsp;기업의 주가 분석을 위해 미리 주식 데이터를 저장한다. 여기엔 **KOSPI 100**를 구성하는 한국 기업과 **뉴욕증권거래소(NYSE), 나스닥(NASDAQ)**에 상장된 시가총액 100위까지의 미국기업들이 포함된다. **yfinance API**를 활용하여 수집하였으며, 기간은 2년(2023년 7월~)이다. 저장되는 데이터는 ticker(식별 기호)와 기업명, 매일 장이 끝날때의 종가와 거래량이다. 또한 주가에 지대한 영향을 끼치는 것으로 판단되는 주요 지표(인덱스) 지수도 수집한다. 주요 지표로는 S&P500, 나스닥100, 다우존스 인터넷 지수, 코스피, 코스닥, CBOE 변동성 지수, 미국 10년 만기 국채 금리, 미국 연방기금 금리, 한국은행 기준 금리, 환율, WTI 원유 선물, 필라델피아 반도체 지수, 리튬 ETF 지수, 나스닥 바이오테크놀로지 지수, 다우존스 산업평균지수가 해당된다. 기업 주가와 동일한 방식으로 수집 및 저장하였다.

#### ④ `기업 설명 요약문, 텍스트 임베딩`
 &nbsp;**yfinance API**을 통해 **KOSIS 100**와 **미국 시총 100** 기업, 주요 지표들에 대한 설명문을 추출하였다. 이것은 해당 기업과 관련있는 뉴스를 추출할 때 1차로 사용된다. 따라서 동일하게 768차원으로 임베딩을 하여 **RAG 코사인 유사도**에 활용하도록 하였다. 또한 영문으로 이루어진 것을 **HyperCLOVA X**를 사용하여 한국어로 번역하였다. 이것은 서비스 제공 시 추가 설명을 사용자에게 제공하기 위해서다.

### 2.2.2 웹 백엔드

#### ① `데이터 준비 에이전트`
 &nbsp;`웹 백엔드`에서 `data_prep_agent.py`에 해당한다. 이것은 네개의 에이전트 중 처음으로 작동한다. 사용자가 분석하기 원하는 기업을 선택하였을 경우, `AnalysisState`객체를 불러오고 기업의 **ticker**를 저장한다. 이후 이를 기준으로 해당되는 **기업의 이름, 기업 설명문, 건전성 보고서**를 호출한 뒤 해당 객체에 누적 저장한다.

#### ② `뉴스 분석 에이전트`
 &nbsp;`웹 백엔드`에서 `news_analyst_agent.py`, `domestic_news_analyst_agent.py`에 해당한다.  `AnalysisState`객체로부터 임베딩 처리된 기업 설명문을 기준으로, 데이터베이스에 저장된 수많은 해외, 국내 금융 뉴스 중 **RAG 유사도검색**을 통해 **1차적으로 각각 15개의 후보**를 선정한다. 이것은 벡터를 기준으로 의미적으로 가장 유사한 문장을 찾는 것이기 때문에 속도와 자원 활용면에서 이득이 많다. 그 다음, **Gemini AI**를 활용하여 해당 기업과 연관이 있다고 판단되는 뉴스를 각각 **최종 3개**를 선택한다. 또한 이 뉴스들과 관련있는 미국 기업과 주요 지표들도 추가로 반환하도록 한다. LLM 모델의 프롬프트에 ‘json형태로 ``결과를 생성하라’고 지정한 다음, 이를 **파싱**(Parsing)함으로서 구현할 수 있었다. 마지막으로 이 정보들을  `AnalysisState`객체에 저장하여 다음 에이전트로 넘어간다. 이것은 본 프로젝트의 주된 목표인 **유리상자**의 핵심 과정으로서 AI의 환각현상을 최소화하고, 분석 과정을 들여다 볼 수 있게 해준다.

#### ③ `시장 데이터 분석 에이전트`
 &nbsp;`웹 백엔드`에서 `market_correlation_agent.py`에 해당한다. 이것은 분석 대상인 기업과, `뉴스 분석 에이전트`를 통해 선정된 관련 기업, 주요 지표들의 **주가 데이터**를 데이터베이스에서 불러오는 기능을 한다. 또한 프론트엔드에서 동적인 그래프를 생성할 수 있도록 장기 추이 데이터(2023년 7월부터 현재까지)와 단기 반응 데이터(뉴스 발생 시점 전후) 두 형태로 가공한다. 이때 단기 데이터를 위하여, 7일 이내에 발생한 뉴스들을 하나의 블록으로 묶고, 앞뒤로 일주일 간격을 계산한다.
 
#### ④ `최종 보고서 생성 에이전트`
 &nbsp;`웹 백엔드`에서 `report_synthesizer_agent.py`에 해당한다. 앞서 `AnalysisState`객체에 축적한 모든 데이터를 입력으로 받는다. 이후 **HyperCLOVA X**모델을 사용하여 최종 보고서를 작성한다. 보고서 작성을 세가지 LLM으로 나누어 작업을 부여함으로써, 보다 논리적이고 구체적인 결과물을 얻을 수 있다. 하나의 LLM만을 가지고 보고서를 작성할 시, 최대 생성 토큰수가 부족해지거나 환각현상이 심해지는 경우가 자주 발생하기 때문에 이것을 미리 방지하기 위함이다. 모든 작성이 완료되면 `AnalysisState`객체에 담아 웹 프론트엔드에 전달하며 파이프라인을 종료시킨다.

##### 분석가 LLM
 &nbsp;뉴스 분석을 통해 얻은 관련 기업과 주요지표에 대하여, 분석 대상 기업에 대한 **영향도**를 분석한다. 기업과 지표의 설명문, 뉴스 요약문이 활용되며 관련 주체의 개수만큼 반복된다.
##### 전략가 LLM
 &nbsp;`분석가 LLM`에서 생성된 분석 내용과 금융 뉴스, 주가 데이터, 기업의 재무 건전성 보고서를 입력으로 받는다. 이후 관련 기업과 주요 지표에 대해 긍정 또는 부정요인을 파악한 후 3문장의 요약문을 작성한다. 마찬가지로 관련 주체의 개수만큼 반복된다.
##### 요약가 LLM
 &nbsp;마지막으로 모든 LLM에서 나온 결과물을 종합하여, 개인 투자자의 입장에서 의사결정에 도움을 줄 수 있는 최종 보고서를 작성한다.

### 2.2.3 웹 프론트엔드
 &nbsp; 사용자가 서비스를 실행하면 보여지는 화면이다. 이곳 웹 프론트엔드에서 자신의 포트폴리오와 **분석을 진행할 기업**을 선택할 수 있다. 백엔드에서 분석을 완료 후 그 결과는 다시 시각화되어 보여진다. 본 서비스의 프로토타입은 `HTML`, `CSS`, `JavaScript` 등 기본적인 기술을 사용해 제작하였다. 그중 `Socket.IO`는 백엔드 서버와의 실시간 통신을 담당한다. 각 진행사항은 로딩화면에 표시되고, 최종 보고서가 생성되면 화면에 업데이트되어 표시된다. 또한 `Chart.js`는 가공된 주가 데이터를 받아 동적인 그래프로 시각화한다. **장기**(2년)/**단기**(뉴스)로 구분되어지며 사용자와의 상호작용이 강화되어 쉽게 이해할 수 있다. 

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
| `data_prep_agent.py` | 사용자가 요청한 기업의 재무 건전성 보고서를 데이터베이스에서 가져와 분석의 기초를 마련하는 에이전트 |
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

### us_stocks
yfinance API 미국 시총 100 주가 추출  

| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| `time` | 날짜 | timestamptz |  
| `ticker` | 기업 식별 기호 | text |  
| `company_name` | 기업명 | text |  
| `close_price` | 종가 | numeric |
| `volume` | 거래량 | int8 |
| `created_at` | 추출시간 | timestamptz |
