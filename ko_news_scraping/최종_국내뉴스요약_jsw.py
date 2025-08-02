import os
import pandas as pd
import numpy as np
import time
import json
from datetime import timedelta
import datetime
##뉴스스크랩
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dateutil.parser import parse
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
## API 구동
import http.client
import uuid
from supabase import create_client, Client
from google import genai
from google.genai import types
import pytz

##############################
# 1. 연합뉴스 리스트 크롤링

def crawl_yesterday_news():
    """
    연합뉴스 국내증시 섹션에서 어제 작성된 기사를 크롤링하여 DataFrame으로 반환합니다.
    """
    
    # 1. 날짜 및 시간대 설정
    # 한국 시간대(UTC+9)를 기준으로 설정합니다.
    tz = pytz.timezone('Asia/Seoul')
    
    # 전날 뉴스만을 추출한다
    # 모든 뉴스 데이터를 수집하고 중복 제거하는것은 자원이 많이 소모됨
    # 어제 날짜를 계산합니다.
    yesterday = (datetime.datetime.now(tz) - datetime.timedelta(days=1)).date()
    current_year = yesterday.year
    
    print(f"크롤링 대상 날짜: {yesterday.strftime('%Y-%m-%d')}")

    # 2. 추출한 데이터를 저장할 리스트
    news_data = []
    
    # 3. 웹 페이지 순회 및 데이터 추출
    MAX_PAGES_TO_CRAWL = 10  # 크롤링할 최대 페이지 수
    stop_crawling = False # 크롤링 중단 플래그

    for page_num in range(1, MAX_PAGES_TO_CRAWL + 1): # 각 페이지별로
        if stop_crawling: # 어제 날짜보다 오래된 기사가 존재한다면 그 페이지까지 진행
            break

        # 연합뉴스 국내증시
        url = f'https://www.yna.co.kr/market-plus/domestic-stock/{page_num}'
        print(f"크롤링 시도... 페이지: {page_num}")
        
        try:
            # 크롤링 user-agent 설정
            headers = { 
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 기사 정보를 담고 있는 div.news-con 태그를 모두 선택
            article_containers = soup.select('div.news-con')
            
            # 현재 페이지에 기사 컨테이너가 없으면 중단
            if not article_containers:
                print(f"페이지 {page_num}에서 기사 컨테이너(div.news-con)를 찾지 못해 크롤링을 중단합니다.")
                break

            for article_con in article_containers:
                time_tag = article_con.select_one('span.txt-time') # 날짜
                title_anchor = article_con.select_one('a.tit-news') # 제목 및 링크

                # 필수 요소가 없으면 해당 기사는 건너뛰기 (오류 또는 광고)
                if not time_tag or not title_anchor:
                    continue
                
                time_str = time_tag.get_text(strip=True)
                
                # 4. 날짜 필터링
                # 어제에 해당되는 날짜만 추출하기 위해
                try:
                    # 기사 날짜
                    # 연도, 월, 일까지만 추출
                    article_date = datetime.datetime.strptime(f"{current_year}-{time_str}", '%Y-%m-%d %H:%M').date()
                    
                    # 기사 날짜가 어제와 같으면 데이터 추가
                    if article_date == yesterday:
                        title_span = title_anchor.select_one('span.title01')
                        # 제목 태그가 없는 경우를 대비
                        if not title_span:
                            continue
                            
                        title = title_span.get_text(strip=True)
                        
                        # 제목이 '[속보]'로 시작하는 기사는 건너뛰기.
                        # 이것은 내용이 없다
                        if title.startswith('[속보]'):
                            continue
                        
                        link = title_anchor['href']
                        
                        datetime_for_db = datetime.datetime.strptime(f"{current_year}-{time_str}", '%Y-%m-%d %H:%M').strftime('%Y-%m-%d %H:%M:%S')
                        
                        news_data.append({
                            'title': title,
                            'date': datetime_for_db,
                            'url': link
                        })
                    
                    # 기사 날짜가 어제보다 오래되었으면 모든 페이지 탐색 중단
                    elif article_date < yesterday:
                        stop_crawling = True
                        break # 현재 페이지의 나머지 기사 처리를 중단

                except ValueError:
                    # 날짜 형식 변환 중 오류가 발생하면 해당 기사는 건너뛰기
                    continue
            
            if stop_crawling:
                print(f"페이지 {page_num}에서 대상 날짜보다 오래된 기사를 발견하여 크롤링을 중단합니다.")
                break

        except requests.exceptions.RequestException as e:
            print(f"페이지를 가져오는 중 오류 발생: {url}, 오류: {e}")
            break
            
    # 5. 결과 저장용 데이터프레임 생성
    if not news_data:
        print("최대 페이지까지 탐색했지만 어제 날짜에 해당하는 기사를 찾지 못했습니다.")
        return pd.DataFrame()
        
    df = pd.DataFrame(news_data)
    
    return df

# 6. 웹크롤링 함수 실행
news_df = crawl_yesterday_news()

# 7. 전처리
# 시간대 변환
## timestamptz에 저장할려면 UTC+0으로 변환해야함
news_df['publish_date'] = pd.to_datetime(news_df['date'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
news_df['publish_date'] = news_df['publish_date'].dt.tz_localize('Asia/Seoul')
news_df['publish_date'] = news_df['publish_date'].dt.tz_convert('UTC')

#################################
# 2. 뉴스 본문 크롤링
# 웹크롤링된 모든 html은 news_df에 존재한다
def get_news_content(url):
    """
    주어진 URL에서 연합뉴스 기사 본문을 추출합니다.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 요청이 성공했는지 확인
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 기사 본문 컨테이너 선택
        # '#articleWrap > div.story-news.article'에 기사 본문이 존재
        content_container = soup.select_one('#articleWrap > div.story-news.article')
        
            
        if content_container:
            # 컨테이너 안의 모든 p 태그 텍스트 추출
            paragraphs = content_container.select('p')
            # 모든 문단을 하나의 문자열로 합치기
            article_text = " ".join([p.get_text(strip=True) for p in paragraphs[:-2]]) # 마지막 두 문단은 제외 # 기자명같은 부수적인 데이터가 존재함
            return article_text
        else:
            return pd.NA
            
    except requests.exceptions.RequestException as e:
        return f"오류 발생: {e}"
    
# 함수 실행
news_df["content"]=news_df.apply(lambda row: get_news_content(row['url']), axis=1)

##################################
# 3. 뉴스 요약

# 뉴스 요약은 CLOVA X API를 사용하여 진행한다
class CompletionExecutor:
    def __init__(self, host, api_key, request_id):
        self._host = host
        self._api_key = api_key
        self._request_id = request_id

    def execute(self, completion_request):
        """
        API를 실행하고 스트리밍 응답에서 [DONE] 직전의 최종 content를 추출하여 반환합니다.
        자세한 설명은 '주식 추출' 항목 참조
        """
        headers = {
            'Authorization': self._api_key,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'text/event-stream'
        }
        
        with requests.post(self._host + '/testapp/v3/chat-completions/HCX-DASH-002',
                           headers=headers, json=completion_request, stream=True) as r:
            
            final_content = None # 최종 content를 저장
            
            for line in r.iter_lines():
                if not line:
                    continue

                decoded_line = line.decode('utf-8')
                

                if 'data: [DONE]' in decoded_line:
                    break
                
                if decoded_line.startswith('data:'):
                    try:
                        json_str = decoded_line[len('data:'):].strip()
                        data = json.loads(json_str)
                        if 'message' in data and 'content' in data['message']:
                            if data['message']['content']:
                                final_content = data['message']['content']
                    except (json.JSONDecodeError, KeyError): # 오류 발생 시
                        continue
                        
        return final_content

def analyze_news_content(content):
    """
    뉴스 본문을 받아 LLM API로 요약, 주요 기업, 이벤트를 JSON 형식으로 요청하고 파싱하여 반환합니다.
    자세한 설명은 '주식 추출' 항목 참조
    """
    if not isinstance(content, str) or not content.strip():
        return "내용 없음"

    # LLM API 호출을 위한 인스턴스 생성
    api_key_with_bearer = f'Bearer {os.environ.get("CLOVA_API_KEY")}'
    completion_executor = CompletionExecutor(
        host='https://clovastudio.stream.ntruss.com',
        api_key=api_key_with_bearer,
        request_id=os.environ.get("CLOVA_REQUEST_ID")
    )

    # 프롬프트와 입력 내용
    preset_text = [
        {"role":"system","content":"너는 증권 분석가야. 아래 영어 뉴스 본문을 분석하고, 금융 및 증권 분석에 필요한 핵심 정보만 담아서 한국어 세 문장으로 요약해줘. (긍정, 부정, 중립적 뉘앙스 포함)"},
        {"role":"user","content": content}
    ]

    # API 옵션
    request_data = {
        'messages': preset_text,
        'topP': 0.8,
        'topK': 0,
        'maxTokens': 256, # 요약 길이를 고려한 토큰 수 조정
        'temperature': 0.5,
        'repetitionPenalty': 1.1,
        'stop': [],
        'includeAiFilters': True,
        'seed': 0
    }

    try:
        result = completion_executor.execute(request_data)
        time.sleep(0.5)
        return result if result else "응답 없음"

    except Exception as e:
        print(f"API 처리 중 오류 발생: {e}")
        # 오류 발생 시에도 단일 문자열 반환
        return "오류 발생"
    
# 함수 실행
news_summary = news_df.copy()
news_summary["summary"] = news_summary['content'].apply(analyze_news_content)

################################
# 4. 벡터화 (임베딩)
# 벡터화는 Google Gemini API를 사용하여 진행
API_KEY = os.environ.get("GEMINI_API_KEY")

def get_summary_embedding(summary_text: str, client: genai.Client) -> list[float] | None:
    """
    하나의 요약본 텍스트를 받아 임베딩 벡터를 반환하는 함수.
    자세한 설명은 '기업 설명 한글번역' 항목 참조
    """
    # 1. 요약본 내용이 비어있는지 확인
    if not summary_text or pd.isna(summary_text):
        return None
    
    try:
        # 2. 'contents'가 아닌 'content' 파라미터로 단일 텍스트를 전달
        result = client.models.embed_content(
            model="models/text-embedding-004",
            contents=summary_text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        # 3. 결과 객체에서 .embedding 속성으로 벡터를 직접 반환
        vectors = [obj.values for obj in result.embeddings]
        vectors=vectors[0]

        return vectors
    
    except Exception as e:
        print(f"API Error embedding '{summary_text[:50]}...': {e}")
        return None


# API 실행
if __name__ == "__main__":
    client = genai.Client(api_key=API_KEY)
    news_summary['embedding'] = news_summary['summary'].apply(lambda text: get_summary_embedding(text, client))

#######################################
# 5. Supabase에 저장
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

# 저장에 사용할 데이터프레임
df=news_summary[["title","publish_date","url","summary","embedding"]]

try:
    supabase: Client = create_client(supabase_url, supabase_key)
    print("Supabase에 연결하여 기존 데이터를 확인합니다.")

    # 기존의 뉴스 데이터와 비교하여 중복처리하지 않기 위한 로직
    # 1) DB에 저장된 모든 'title' 목록을 가져오기
    response = supabase.table('ko_financial_news_summary').select('title').execute()
    existing_titles = {item['title'] for item in response.data}
    print(f"현재 DB에 {len(existing_titles)}개의 기사가 있습니다.")

    # 2) 새로 생성된 DataFrame에서 이미 있는 title들을 제외
    new_articles_df = df[~df['title'].isin(existing_titles)]

    if new_articles_df.empty:
        print("추가할 새로운 기사가 없습니다.")
    else:
        print(f"{len(new_articles_df)}개의 새로운 기사를 찾았습니다. 업로드를 준비합니다.")

    
        # 업로드 형식으로 변환
        records_to_upload = new_articles_df.to_dict('records')
        for record in records_to_upload:
            record['publish_date'] = record['publish_date'].isoformat()
        
        # 데이터 삽입
        data, count = supabase.table('ko_financial_news_summary').insert(records_to_upload).execute()
        print(f"🎉 성공적으로 {len(data[1])}개의 새 기사를 업로드했습니다.")

except Exception as e:
    print(f"❌ 작업 중 오류 발생: {e}")
