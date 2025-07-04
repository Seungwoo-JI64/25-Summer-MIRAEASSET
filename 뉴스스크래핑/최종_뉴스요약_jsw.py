#라이브러리
##기본 작업
import os
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime, timedelta
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

###########################################################
# 1. 뉴스 리스트 추출

def parse_time_ago(time_str):
    """
    'X minutes/hours ago' 형태의 시간 문자열을 파싱하여 timedelta 객체로 변환합니다.
    예: "Reuters•13 hours ago" -> timedelta(hours=13)
    """
    # "Reuters•" 같은 발행사 정보 제거
    if '•' in time_str:
        time_str = time_str.split('•')[1].strip()

    # 정규표현식을 사용하여 숫자와 시간 단위(minute, hour)를 찾습니다.
    match = re.search(r'(\d+)\s+(minute|hour)s?\s+ago', time_str, re.IGNORECASE)
    
    if match:
        value = int(match.group(1))
        unit = match.group(2).lower()
        
        if unit == 'minute':
            return timedelta(minutes=value)
        elif unit == 'hour':
            return timedelta(hours=value)
            
    return None

def get_all_news_links(base_urls):
    """
    주어진 모든 URL 페이지에서 12시간 이내에 작성된
    모든 기사의 제목과 링크를 수집하고 중복을 제거합니다.
    """
    # Selenium WebDriver 설정
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # 브라우저 창을 띄우지 않음
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    unique_articles = {}

    for url in base_urls:
        print(f"'{url}' 페이지에서 기사 목록을 수집하는 중...")
        driver.get(url)
        
        # WebDriverWait 객체 생성 (타임아웃 10초)
        wait = WebDriverWait(driver, 10)
        
        try:
            # 페이지 로딩 대기: 최소 1개의 기사 아이템이 로드될 때까지
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.stream-item.story-item")))
        except TimeoutException:
            print(f"'{url}' 페이지에서 기사를 찾을 수 없거나 로딩에 실패했습니다.")
            continue

        # 스크롤을 끝까지 내림
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                # scrollHeight가 변경될 때까지 (최대 10초) 대기
                wait.until(lambda d: d.execute_script("return document.body.scrollHeight") > last_height)
                # 새로운 높이로 업데이트
                last_height = driver.execute_script("return document.body.scrollHeight")
            except TimeoutException:
                # 높이 변경이 없으면 더 이상 로드할 콘텐츠가 없는 것이므로 반복 종료
                break

        # 페이지 소스를 BeautifulSoup으로 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 기사 목록 (li 태그) 찾기
        news_list = soup.select('li.stream-item.story-item')

        for item in news_list:
            title_tag = item.select_one('h3')
            link_tag = item.select_one('a.subtle-link')
            # 발행 시간 정보를 담고 있는 div 태그 선택
            time_tag = item.select_one('div.publishing')

            if title_tag and link_tag and link_tag.has_attr('href') and time_tag:
                time_str = time_tag.get_text(strip=True)
                
                # 발행 시간을 파싱
                time_delta = parse_time_ago(time_str)
                
                # 파싱에 성공했고, 12시간 이내인 경우에만 추가
                if time_delta and time_delta <= timedelta(hours=12):
                    title = title_tag.get_text(strip=True)
                    link = "https://finance.yahoo.com" + link_tag['href']

                    # 제목을 기준으로 중복 제거
                    if title not in unique_articles:
                        unique_articles[title] = {"url": link, "time": time_str}

    driver.quit()
    
    # 결과를 리스트 형태로 변환
    article_list = [{"title": title, "url": data["url"], "time": data["time"]} for title, data in unique_articles.items()]
    print(f"총 {len(article_list)}개의 12시간 이내 기사를 찾았습니다.")
    return article_list

# 대상 URL 목록
target_urls = [
    "https://finance.yahoo.com/topic/latest-news/",
    "https://finance.yahoo.com/topic/stock-market-news/",
    "https://finance.yahoo.com/topic/yahoo-finance-originals/",
    "https://finance.yahoo.com/topic/economic-news/",
    # "https://finance.yahoo.com/topic/earnings/",
    # "https://finance.yahoo.com/topic/tech/",
    "https://finance.yahoo.com/topic/electric-vehicles/"
]

# 함수 실행
news_list = get_all_news_links(target_urls)

##############################################
# 2. 뉴스 스크랩

def get_article_details(article_list):
    """
    뉴스 목록을 받아 각 기사의 본문과 게시 날짜를 추출합니다.
    즉, 각 뉴스의 링크에 접속하여 본문과 게시 날짜를 추출한다.
    """ 
    final_results = [] #최종 결과 저장 리스트
    
    for i, article in enumerate(article_list):
        print(f"({i+1}/{len(article_list)}) '{article['title']}' 기사 처리 중...") #작업 확인용
        
        #앞서 수집한 링크는 주소가 이상하게 되어있어서 수정하는 작업이 필요하다
        url_to_fetch = article['url']
        if url_to_fetch.count('https://finance.yahoo.com') > 1:
            url_to_fetch = 'https://finance.yahoo.com' + url_to_fetch.split('https://finance.yahoo.com')[-1]
        
        # 뉴스 본문 수집
        retries = 3 #실패했을 경우 세번 반복
        for attempt in range(retries):
            try:
                response = requests.get(url_to_fetch, headers={'User-Agent': 'Mozilla/5.0'})
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser') #html 파싱

                # 1. 본문 추출
                content_parts = []
                body_wrappers = soup.select('div.atoms-wrapper, div.read-more-wrapper') #본문은 두개의 태그에 저장되어있다.
                for wrapper in body_wrappers:
                    content_parts.append(wrapper.get_text(separator=' ', strip=True)) #div안에 여러개의 태그로 본문 단락이 분리되어있다. 따라서 이것을 합치는 과정이다.
                content = ' '.join(content_parts)

                # 2. 게시 날짜 추출 및 형식 변환
                time_tag = soup.select_one('time')
                publish_date_str = "N/A"
                if time_tag and time_tag.has_attr('datetime'):
                    dt_object = parse(time_tag['datetime'])
                    publish_date_str = dt_object.strftime('%Y-%m-%d %H:%M')

                # 결과 리스트에 추가
                final_results.append({
                    "title": article['title'], #제목
                    "publish_date": publish_date_str, #게시 날짜
                    "url": url_to_fetch, #기사 링크
                    "content": content #본문 내용
                })
                
                time.sleep(2) # 성공 시 요청 간격을 2초로 늘림
                break # 성공했으므로 재시도 루프 탈출

            # HTTP 오류가 발생했을 경우 재시도
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    wait_time = 10
                    print(f"  [알림] 429 오류 발생. {wait_time}초 후 재시도합니다... ({attempt + 1}/{retries})")
                    time.sleep(wait_time)
                else:
                    print(f"  [오류] HTTP 오류 발생: {e}")
                    break # 다른 HTTP 오류는 재시도하지 않음
            except requests.exceptions.RequestException as e:
                print(f"  [오류] 기사 접근 중 오류 발생: {e}")
                break # 일반적인 요청 오류는 재시도하지 않음
            except Exception as e:
                print(f"  [오류] 기사 처리 중 예외 발생: {e}")
                break
        else: # for 루프가 break 없이 끝났을 경우 (모든 재시도 실패)
            print(f"  [실패] 모든 재시도에 실패하여 다음 기사로 넘어갑니다.")
            
    return final_results

# 함수 실행
# 이전에 생성된 news_list를 그대로 사용합니다.
full_news_data = get_article_details(news_list)

# 최종 결과 생성 (데이터프레임으로 변환)
df = pd.DataFrame(full_news_data)
# df['publish_date'] = pd.to_datetime(df['publish_date'], errors='coerce') + pd.Timedelta(hours=9) # 한국 시간으로 변환 UTC+9
print("--- 최종 뉴스 스크래핑 완료")
###############################################################
# 3. 뉴스 요약

# 뉴스 요약은 CLOVA X API를 사용하여 진행한다.
## 따라서 공식으로 제공되는 예제를 수정하여 클래스를 미리 생성해야한다.
class CompletionExecutor:
    def __init__(self, host, api_key, request_id):
        self._host = host
        self._api_key = api_key
        self._request_id = request_id

    def execute(self, completion_request):
        """
        API를 실행하고 스트리밍 응답에서 [DONE] 직전의 최종 content를 추출하여 반환합니다.
        """
        headers = {
            'Authorization': self._api_key,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'text/event-stream'
        }
        
        # 원래 사용하던 엔드포인트
        with requests.post(self._host + '/testapp/v3/chat-completions/HCX-DASH-002',
                           headers=headers, json=completion_request, stream=True) as r:
            
            final_content = None # 최종 content를 저장할 변수
            
            for line in r.iter_lines():
                if not line:
                    continue

                decoded_line = line.decode('utf-8')
                
                # 스트림의 끝을 나타내는 '[DONE]' 메시지를 확인하면 루프 종료
                ## 각각의 토근을 받아오는 형태이고, 마지막에 이 결과를 종합한것을 따로 출력한다.
                if 'data: [DONE]' in decoded_line:
                    break
                
                if decoded_line.startswith('data:'):
                    try:
                        # 내가 프롬프트를 통해 결과를 json으로 반환하라고 하였다.
                        ## 따라서 json 파싱을 진행한다.
                        json_str = decoded_line[len('data:'):].strip()
                        data = json.loads(json_str)
                        
                        # message 객체와 content가 있는지 확인
                        if 'message' in data and 'content' in data['message']:
                            # content가 비어있지 않은 경우, 이 내용을 최종 결과로 덮어씁니다.
                            # 스트리밍 중 마지막 유효한 content가 최종 결과일 가능성이 높습니다.
                            if data['message']['content']:
                                final_content = data['message']['content']
                    except (json.JSONDecodeError, KeyError):
                        # 파싱 오류나 키 오류가 발생하면 해당 라인은 무시하고 계속 진행
                        continue
                        
        return final_content

def analyze_news_content(content):
    """
    뉴스 본문을 받아 LLM API로 요약, 주요 기업, 이벤트를 JSON 형식으로 요청하고 파싱하여 반환합니다.
    """
    if not isinstance(content, str) or not content.strip():
        return "내용 없음", "내용 없음", "내용 없음"

    # LLM API 호출을 위한 인스턴스 생성
    completion_executor = CompletionExecutor(
        host='https://clovastudio.stream.ntruss.com',
        api_key='Bearer nv-3da49e910a8b4d3b99721dab49141e35xINY', # 이것은 테스트키이므로 나중에 사업용 키를 받았을 경우 대체한다.
        request_id='b006c788142a49a9adf34e73d6b0a403' # API를 구별해주는 ID
    )

    # API에 전달할 메시지 구성 (JSON 형식으로 응답 요청)
    preset_text = [
        # 프롬프트
        {"role":"system","content":"너는 증권 분석가야. 아래 영어 뉴스 본문을 분석해서 다음의 작업을 수행해줘.\n1. 금융 및 증권 분석에 필요한 핵심 정보만 담아서 한국어 세 문장으로 요약해줘. (긍정, 부정, 중립적 뉘앙스 포함)\n2. 뉴스에 언급된 주요 기업명을 추출해줘. (쉼표로 구분)\n3. 뉴스의 핵심 이벤트를 명사 형태로 추출해줘. (쉼표로 구분)\n\n결과는 반드시 아래와 같은 JSON 형식으로만 생성하고, 다른 어떤 설명도 붙이지 마.\n```json\n{\"summary\": \"요약 내용\", \"company\": \"기업명1, 기업명2\", \"event\": \"이벤트1, 이벤트2\"}\n```"},
        # 입력할 데이터 내용
        {"role":"user","content": content}
    ]

    # API 옵션 (기본값 사용)
    request_data = {
        'messages': preset_text,
        'topP': 0.8,
        'topK': 0,
        'maxTokens': 256, # 요약 길이를 고려하여 토큰 수 증가
        'temperature': 0.5,
        'repetitionPenalty': 1.1,
        'stop': [],
        'includeAiFilters': True,
        'seed': 0
    }

    try:
        # API 실행 및 결과 받기
        result = completion_executor.execute(request_data)
        time.sleep(0.5) # API 요청 간 지연

        if result:
            # LLM 응답에서 불필요한 마크다운 코드 블록과 공백을 제거합니다.
            clean_result = result.replace("```json", "").replace("```", "").strip()
            
            try:
                # 깨끗해진 문자열을 JSON으로 파싱
                data = json.loads(clean_result)
                summary = data.get("summary", "파싱 실패")
                company = data.get("company", "파싱 실패")
                event = data.get("event", "파싱 실패")
                return summary, company, event
            except json.JSONDecodeError:
                return "JSON 파싱 실패", "JSON 파싱 실패", "JSON 파싱 실패"
        else:
            return "응답 없음", "응답 없음", "응답 없음"

    except Exception as e:
        print(f"API 처리 중 오류 발생: {e}")
        return "오류 발생", "오류 발생", "오류 발생"
    

df_sample = df.copy() # 앞서 수집한 뉴스 데이터
# 뉴스 본문을 입력한다.
new_columns = df_sample['content'].apply(lambda x: pd.Series(analyze_news_content(x)))
new_columns.columns = ['summary', 'company', 'event']

# 기존 데이터프레임에 새로운 열들 병합
df_final = pd.concat([df_sample, new_columns], axis=1)
print("--- 요약 및 분석 결과 생성 완료---")

# 최종 요약 결과 생성
news_summary=pd.merge(df, df_final[['title', 'summary', 'company', 'event']], on='title', how='inner')
news_summary.drop(columns=["content"], inplace=True)

#####################################################
# 이 아래 4, 5번은 RAG를 위한 벡터화 작업이다.
#####################################################
# 4. 문단 나누기

# API 실행 클래스
class CompletionExecutor:
    def __init__(self, host, api_key, request_id):
        self._host = host
        self._api_key = api_key
        self._request_id = request_id

    def _send_request(self, completion_request):
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': self._api_key,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id
        }

        conn = http.client.HTTPSConnection(self._host)
        conn.request('POST', '/serviceapp/v1/api-tools/segmentation', json.dumps(completion_request), headers)
        response = conn.getresponse()
        result = json.loads(response.read().decode(encoding='utf-8'))
        conn.close()
        return result

    def execute(self, completion_request):
        res = self._send_request(completion_request)
        if res['status']['code'] == '20000':
            # API 응답의 'topicSeg'가 이미 텍스트의 리스트이므로, 추가 처리 없이 그대로 반환합니다.
            return res['result']['topicSeg']
        else:
            print(f"API Error: {res}")
            return [] # 오류 발생 시 빈 리스트 반환


# 데이터프레임의 요약본을 문단으로 나눈다
def segment_news_summary(summary_text):
    """하나의 요약본 텍스트를 받아 문단 나누기 API를 호출하고 결과를 반환합니다."""
    if not isinstance(summary_text, str) or not summary_text.strip():
        return []

    completion_executor = CompletionExecutor(
        host='clovastudio.stream.ntruss.com',
        api_key='Bearer nv-954d9d9843374384bfe278a5169c2ee18Q6C', #테스트키이므로 후에 사업용키로 대체
        request_id='37e746486492410dab50545828f1edfb' # API 구분 ID
    )

    # API 기본 옵션
    request_data = {
        "postProcessMaxSize": 1000,
        "alpha": 0.0,
        "segCnt": -1,
        "postProcessMinSize": 300,
        "text": summary_text,
        "postProcess": False
    }
    
    # API 요청 간의 과부하를 막기 위해 약간의 지연 시간 추가
    time.sleep(0.5)
    
    return completion_executor.execute(request_data)


# 문단 나누기 실행
print("뉴스 요약본에 대한 문단 나누기를 시작합니다...") # 진행 확인용
# 'summary' 열의 각 텍스트에 대해 문단 나누기 함수를 적용하고, 결과를 새 열에 저장
news_summary['segmented_summary'] = news_summary['summary'].apply(segment_news_summary)
print("문단 나누기 작업이 완료되었습니다.")

############################################3
# 5. 벡터화 (임베딩)

# API 실행 클래스
class EmbeddingExecutor:
    def __init__(self, host, api_key):
        self._host = host
        self._api_key = api_key

    def _send_request(self, completion_request, request_id):
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': self._api_key,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': request_id
        }
        try:
            conn = http.client.HTTPSConnection(self._host)
            conn.request('POST', '/serviceapp/v1/api-tools/embedding/clir-emb-dolphin', json.dumps(completion_request), headers)
            response = conn.getresponse()
            result = json.loads(response.read().decode(encoding='utf-8'))
            conn.close()
            return result
        except Exception as e:
            return {'status': {'code': 'N/A', 'message': str(e)}}

    def execute(self, completion_request):
        request_id = str(uuid.uuid4())
        res = self._send_request(completion_request, request_id)
        if res.get('status') and res['status'].get('code') == '20000':
            return res.get('result', {}).get('embedding', [])
        else:
            status = res.get('status', {})
            code = status.get('code', 'Unknown')
            message = status.get('message', 'No error message returned.')
            print(f"Error (Code: {code}): {message}")
            return []

# 텍스트 조각 임베딩 함수 
def embed_text_segments(segments, executor):
    if not isinstance(segments, list):
        return []
    vectors = []
    for segment in segments:
        if isinstance(segment, str) and segment.strip():
            request_data = {"text": segment.strip()}
            vector = executor.execute(request_data)
            if vector:
                vectors.append(vector)
            time.sleep(0.2)
    return vectors

# 실행
API_KEY = 'Bearer nv-954d9d9843374384bfe278a5169c2ee18Q6C' #테스트키임으로 후에 사업용키로 대체
HOST = 'clovastudio.stream.ntruss.com'

embedding_executor = EmbeddingExecutor(host=HOST, api_key=API_KEY)

print("임베딩을 시작합니다...")
# 문단 나누기 결과를 기반으로 임베딩 진행
news_summary['embedding_vectors'] = news_summary['segmented_summary'].apply(
    lambda x: embed_text_segments(sum(x, []), executor=embedding_executor)
)
print("임베딩 작업이 완료되었습니다.")

#################################################3
# 6. Supabase 데이터베이스에 업로드
## 이미 news_summary라는 테이블을 생성하였다.

# 컬럼명 변경
## 생성한 데이터베이스에 맞게 수정한다.
news_summary.rename(columns={
    'publish_date': 'published_date',
    'company': 'company_name',
    'event': 'event_category'
}, inplace=True)

# 임베딩 벡터 리스트를 단일 평균 벡터로 변환
## 데이터베이스 VECTOR(1024)형식에 맞추기 위함이다
def average_vectors(vectors):
    if not vectors or not isinstance(vectors[0], list):
        return None
    # np.mean을 사용하여 벡터들의 평균을 계산하고 다시 리스트로 변환
    return np.mean(vectors, axis=0).tolist()

# 'embedding' 컬럼 생성
news_summary['embedding'] = news_summary['embedding_vectors'].apply(average_vectors)


# 업로드할 최종 컬럼만 선택
final_df = news_summary[[
    'published_date', 'company_name', 'event_category', 'title', 'summary', 'embedding', "url"
]]

# Supabase에 업로드하기 위해 DataFrame을 'list of dictionaries' 형태로 변환
records_to_upload = final_df.to_dict('records')

# 날짜 형식을 문자열로 변환 (Supabase에서 자동 인식)
# for record in records_to_upload:
#     record['published_date'] = record['published_date'].isoformat()

print("--- 데이터베이스 업로드 준비가 되었습니다. ---")

# Supabase 클라이언트
## 각각 프로젝트의 고유 주소와 키이다
### 이것은 다른 테이블과도 동일하게 공유된다.
supabase_url = "https://hcmniqyaqybzhmzmaumh.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhjbW5pcXlhcXliemhtem1hdW1oIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTE0Mzk5NDgsImV4cCI6MjA2NzAxNTk0OH0.wj3P2BaI9_9LjXPULyKIYja20Xk3TbuqS916Sw83Pdg"

# 데이터 업로드
## 기존에 있는 데이터와 중복되지 않는 데이터만 업로드한다.
try:
    supabase: Client = create_client(supabase_url, supabase_key)
    print("☁️ Supabase에 연결하여 기존 데이터를 확인합니다.")

    # DB에 저장된 모든 'title' 목록을 가져오기
    response = supabase.table('news_summaries').select('title').execute()
    existing_titles = {item['title'] for item in response.data}
    print(f"현재 DB에 {len(existing_titles)}개의 기사가 있습니다.")

    # 새로 생성된 DataFrame에서 이미 있는 title들을 제외
    new_articles_df = news_summary[~news_summary['title'].isin(existing_titles)]

    if new_articles_df.empty:
        print(" 추가할 새로운 기사가 없습니다.")
    else:
        print(f"{len(new_articles_df)}개의 새로운 기사를 찾았습니다. 업로드를 준비합니다.")
        
        # 데이터 전처리 (컬럼명 변경, 임베딩 평균 계산 등)
        new_articles_df = new_articles_df.rename(columns={
            'publish_date': 'published_date', 'company': 'company_name', 'event': 'event_category'
        })
        new_articles_df['embedding'] = new_articles_df['embedding_vectors'].apply(average_vectors)
        
        # (★★★★★) 수정된 부분 (★★★★★)
        # 업로드할 최종 데이터
        final_df = new_articles_df[[
            'published_date',
            'company_name',
            'event_category',
            'title',
            'summary',
            'url',
            'embedding'
        ]]
        
        # 날짜 형식 변환
        ## 이 부분에서 오류가 발생할 수 있다.
        ### 오류가 발생하면 이 과정을 참조 처리하고 진행한다.
        #### 아래의 ❌오류를 확인한다
        records_to_upload = final_df.to_dict('records')
        for record in records_to_upload:
            record['published_date'] = record['published_date'].isoformat()
        
        # 데이터 삽입
        data, count = supabase.table('news_summaries').insert(records_to_upload).execute()
        print(f"성공적으로 {len(data[1])}개의 새 기사를 업로드했습니다.")

except Exception as e:
    print(f"❌❌❌❌❌ 업로드 작업 중 오류 발생: {e} ❌❌❌❌❌")