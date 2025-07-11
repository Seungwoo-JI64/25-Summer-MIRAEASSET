# 25-Summer-MIRAEASSET
2025년 여름방학 B.a.f 미래에셋공모전 서비스부분 DATA TADA팀

# 1. Github 저장 파일 설명
| .github/workflows | 폴더 |  |  
|---|---|---|  
| daily_financial_indices.yml | 깃허브 Actions 증권데이터/지표지수업로드_매일_jsw.py 자동화 | 지승우 |  
| ko_daily_stock_data.yml, us_daily_stock_data.yml | 깃허브 Actions 주식데이터/한국_주식추출_매일_jsw.py, 미국_주식추출_매일_jsw.py 자동화 | 지승우 |  

.
   
| ko_news_scraping | 폴더 | 지승우 |  
|---|---|---|   
| Dockerfile | Render 최종_국내뉴스요약_jsw.py 실행환경 이미지 생성 | 지승우 |  
| requirements.txt | Render 최종_국내뉴스요약_jsw.py 라이브러리 설치 | 지승우 | 
| 최종_국내뉴스요약_jsw.py | Render를 이용하여 매일 UTC+9 8시 금융 뉴스 요약 및 임베딩 자동화 | 지승우 |
.
   
| news_scraping | 폴더 | 지승우 |  
|---|---|---|   
| Dockerfile | Render 최종_영문뉴스요약_jsw.py 실행환경 이미지 생성 | 지승우 |  
| requirements.txt | Render 최종_영문뉴스요약_jsw.py 라이브러리 설치 | 지승우 | 
| 최종_영문뉴스요약_jsw.py | Render를 이용하여 매일 UTC+9 8시, 20시 야후 금융 뉴스 요약 및 임베딩 자동화 | 지승우 |

.
   
| 주식데이터 | 폴더 | 유희준 |  
|---|---|---|   
| 주식추출_2년전_jsw.ipynb | 한국, 미국 시총 100 기업 2년치 주식 수집 (23.07.01~25.07.11) | 유희준, 지승우 |  
| 한국_주식추출_매일_jsw.py, 미국_주식추출_매일_jsw.py | 깃허브 Actions을 활용하여 매일 UTC+9 6시 주식 추출 자동화 | 지승우 | 
| 주식크롤링_yhj.ipynb | 야후 금융 한국, 미국 시총 100 기업 웹크롤링 추출 | 유희준 |
| 기업설명추가_jsw.ipynb | 야후 금융 한국, 미국 시총 100 기업 설명문 추출 | 유희준, 지승우 |

.
   
| 증권데이터 | 폴더 | 서정유 |  
|---|---|---|   
| 2년치지표DB업로드_jsw.ipynb | 한국, 미국 주요 증시지표 2년치 수집 (23.07.01~25.07.11) | 서정유, 지승우 |  
| ~.ipynb | 여러 지표 수집  | 서정유 | 
| 지표지수업로드_매일_jsw.py | 깃허브 Actions을 활용하여 매일 UTC+9 6시 지표 추출 자동화 | 지승우 |

.

| root | 레포지토리 최상단 |  |  
|---|---|---|   
| .env | 주식데이터/주식추출_매일_jsw.py, 기업설명추가_jsw.ipynb 업로드 Supabase, google ai studio 접속 키 저장 | 지승우 |  
| requirements.txt | 깃허브 Actions 구동에 필요한 라이브러리 설치 목록 | 지승우 | 

# 2. Supabase 테이블 목록 

### company_summary : 야후 금융에서 회사 설명 추출
| 피쳐명 | 설명 | 형식 |    
|---|---|---|  
| ticker | 기업 구분 키 | text |   
| company_name | 기업명 | text |  
| summary | 기업 설명문 | text |  
| summary_embedding | 기업 설명문 임베딩 | vector(768) |  

. 

### financial_indices : 야후 금융에서 증시지표 지수 추출
| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| id | 자료 저장 순서 | int8 |  
| index_en | 지표 구분 키 (ticker) | text |  
| index_ko | 지표명(한국어) | text |  
| date | 날짜 | timestamptz |
| value | 지수 | numeric |
| created_at | 추출시간 | timestamptz |  

. 

### financial_news_summart : 야후 금융 뉴스 추출 요약 및 임베딩
| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| id | 자료 저장 순서 | int8 |  
| title | 뉴스 제목 | text |  
| publich_date | 뉴스 발간 일자 | timestamptz |  
| url | 뉴스 링크 | text |
| summary | 뉴스 요약 | text |
| embedding | 뉴스 요약 임베딩 | vector(768) |
| created_at | 추출시간 | timestamptz |

. 

### korean_stocks, un_stocks : 야후 금융 한국, 미국 시총 100 주가 추출
| 피쳐명 | 설명 | 형식 |   
|---|---|---|  
| time | 날짜 | timestamptz |  
| ticker | 기업 구분 키 | text |  
| company_name | 기업명 | text |  
| close_price | 종가 | numeric |
| volume | 거래량 | int8 |
| created_at | 추출시간 | timestamptz |
