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
from google import genai
from google.genai import types



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

    # 정규표현식을 사용하여 숫자와 시간 단위(minute, hour)를 찾기
    ##  (\d+): 하나 이상의 숫자 -> hour 또는 minute, 첫 번째 캡처 그룹(group 1)
    ##  \s+: 하나 이상의 공백 문자
    ##  (minute|hour): 'minute' 또는 'hour' 문자열, 두 번째 캡처 그룹(group 2)
    ##  s?: 's'가 0번 또는 1번 나타남 ('minute'와 'minutes' 모두 대응)
    ##  \s+ago: 공백 후 'ago' 문자열
    ##  re.IGNORECASE: 대소문자를 무시하고 검색
    match = re.search(r'(\d+)\s+(minute|hour)s?\s+ago', time_str, re.IGNORECASE)
    
    # 정규표현식의 결과
    if match:
        value = int(match.group(1)) # 첫 번째 캡처 그룹에서 숫자 추출
        unit = match.group(2).lower() # 두 번째 캡처 그룹에서 단위 추출 (대소문자 구분 없이)
        
        if unit == 'minute': # 시간 단위가 '분'
            return timedelta(minutes=value)
        elif unit == 'hour': # 시간 단위가 '시'
            return timedelta(hours=value)
            
    return None

# 뉴스 웹크롤링 함수
def get_all_news_links(base_urls):
    """
    주어진 모든 URL 페이지에서 12시간 이내에 작성된
    모든 기사의 제목과 링크를 수집하고 중복을 제거합니다.
    """
    unique_articles = {} # 뉴스 목록 저장

    # 여러 페이지에 대하여 뉴스 목록 수집
    # for 루프 안에서 매번 드라이버를 생성하고 종료하도록 구조 변경 <- 파이썬 구동 환경의 부담 줄이기 위해
    for url in base_urls:
        print(f"'{url}' 페이지에서 기사 목록을 수집하는 중...")
        
        # Selenium WebDriver 설정
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.binary_location = "/usr/bin/google-chrome"
        
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)

        try:
            driver.get(url)
            wait = WebDriverWait(driver, 20) # 페이지 로딩 대기 20초
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.stream-item.story-item"))) # 뉴스 항목이 뜰때까지

            # 스크롤 횟수 제한 (최대 10회)
            # 최하단에서 계속 스크롤을 진행해야 뉴스항목이 로드되는 방식
            print("페이지 스크롤을 시작합니다 (최대 10회)...")
            for i in range(10):
                try:
                    last_height = driver.execute_script("return document.body.scrollHeight") # 스크롤 높이 저장
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    WebDriverWait(driver, 15).until( # 스크롤 후 새 콘텐츠가 로드될 때까지 대기
                        lambda d: d.execute_script("return document.body.scrollHeight") > last_height
                    )
                    print(f"스크롤 {i+1}/10 완료, 새 콘텐츠 로드됨.")
                except TimeoutException:
                    print("더 이상 로드할 콘텐츠가 없어 스크롤을 중단합니다.")
                    break
            
            # 페이지 소스를 BeautifulSoup으로 파싱
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            news_list = soup.select('li.stream-item.story-item')

            # 뉴스 항목에서 제목, 링크, 시간 정보 추출
            for item in news_list:
                title_tag = item.select_one('h3') # 제목 태그
                link_tag = item.select_one('a.subtle-link') # 링크 태그
                time_tag = item.select_one('div.publishing') # 시간 태그

                if title_tag and link_tag and link_tag.has_attr('href') and time_tag: # 내용이 존재한다면
                    time_str = time_tag.get_text(strip=True) # 제목 텍스트 추출
                    time_delta = parse_time_ago(time_str) # 시간 문자열 파싱
                    
                    if time_delta and time_delta <= timedelta(hours=12): # 12시간 이내에 작성된 기사만
                        title = title_tag.get_text(strip=True)
                        link = "https://finance.yahoo.com" + link_tag['href']

                        if title not in unique_articles: # 중복 제거
                            unique_articles[title] = {"url": link, "time": time_str}

        except Exception as e:
            print(f"'{url}' 처리 중 오류 발생: {e}")
        finally:
            # try, except와 상관없이 작업이 끝나면 반드시 드라이버 종료
            driver.quit()

    # 결과를 리스트 형태로 변환
    article_list = [{"title": title, "url": data["url"], "time": data["time"]} for title, data in unique_articles.items()]
    print(f"총 {len(article_list)}개의 12시간 이내 기사를 찾았습니다.")
    return article_list

# 뉴스 추출대상 URL 목록
# 전부 야후 파이낸스에서 추출한다
target_urls = [
    "https://finance.yahoo.com/topic/latest-news/",
    "https://finance.yahoo.com/topic/stock-market-news/",
    # "https://finance.yahoo.com/topic/yahoo-finance-originals/",
    # "https://finance.yahoo.com/topic/economic-news/",
    # "https://finance.yahoo.com/topic/earnings/",
    # "https://finance.yahoo.com/topic/tech/",
    "https://finance.yahoo.com/topic/electric-vehicles/"
]

# 함수 실행
news_list = get_all_news_links(target_urls)
news_list = news_list[:100] #한번에 100개, 하루에 총 200개 제한 <- gemini 2.5는 무료이용일 경우 하루에 250번 호출 제한

##############################################
# 2. 뉴스 스크랩

def get_article_details(article_list):
    """
    뉴스 목록을 받아 각 기사의 본문과 게시 날짜를 추출합니다.
    즉, 각 뉴스의 링크에 접속하여 본문과 게시 날짜를 추출한다.
    """ 
    final_results = [] #최종 결과 저장 리스트

    for i, article in enumerate(article_list): # 인덱스와 기사 정보를 동시에 순회
        print(f"({i+1}/{len(article_list)}) '{article['title']}' 기사 처리 중...") #작업 확인용
        
        # 앞서 수집한 링크는 주소가 이상하게 되어있어서 수정하는 작업이 필요하다
        url_to_fetch = article['url']
        if url_to_fetch.count('https://finance.yahoo.com') > 1:
            url_to_fetch = 'https://finance.yahoo.com' + url_to_fetch.split('https://finance.yahoo.com')[-1]
        
        # 뉴스 본문 수집
        retries = 3 # 실패했을 경우 세번 반복
        for attempt in range(retries):
            try:
                response = requests.get(url_to_fetch, headers={'User-Agent': 'Mozilla/5.0'})
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                # 1. 본문 추출
                content_parts = []
                body_wrappers = soup.select('div.atoms-wrapper, div.read-more-wrapper') #본문은 두개의 태그에 저장되어있다.
                for wrapper in body_wrappers:
                    content_parts.append(wrapper.get_text(separator=' ', strip=True)) #div안에 여러개의 태그로 본문 단락이 분리되어있다. 따라서 이것을 합치는 과정이다.
                content = ' '.join(content_parts)

                # 2. 게시 날짜 추출 및 형식 변환
                time_tag = soup.select_one('time') # 뉴스가 게시된 정확한 시간 추출
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
                    break
            except requests.exceptions.RequestException as e:
                print(f"  [오류] 기사 접근 중 오류 발생: {e}")
                break 
            except Exception as e:
                print(f"  [오류] 기사 처리 중 예외 발생: {e}")
                break
        else: 
            print(f"  [실패] 모든 재시도에 실패하여 다음 기사로 넘어갑니다.")
            
    return final_results

# 함수 실행
# 이전에 생성된 news_list를 그대로 사용
full_news_data = get_article_details(news_list)

# 최종 결과 생성
df = pd.DataFrame(full_news_data)
print("--- 최종 뉴스 스크래핑 완료")

###############################################################
# 3. 뉴스 요약

# 환경변수 불러오기
API_KEY = os.environ.get("GEMINI_API_KEY")

def analyze_news_article(article_text: str, api_key: str) -> str:
    """
    하나의 뉴스 기사 텍스트를 받아 Gemini API로 분석하고 결과를 반환하는 함수.
    보내주신 공식 예제 구조를 그대로 따릅니다.
    """
    try:
        client = genai.Client(api_key=api_key) # gemini 클라이언트를 생성
        model = "gemini-2.5-flash" # "gemini-2.5-flash" 모델 사용
        # 프롬프트 구성
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text="""You are an expert stock analyst. Your task is to analyze an English news article and provide a summary.

### INSTRUCTIONS ###
1.  Analyze the provided English news article for key information relevant to investors (e.g., corporate earnings, new products, M&A, regulatory changes).
2.  Create a three-sentence summary in English.
3.  The summary must explicitly state whether the nuance of the news is positive, negative, or neutral for investors.

### EXAMPLES & BEHAVIORAL RULES ###
This is an example of how to behave.

**Example Scenario:** If the user provides instructions but no article to analyze below the "---" line.
**Your Correct Response in this case is this plain text:**
To provide an expert analysis and a three-sentence summary, the news article must be provided. Please submit the English news article for review, and I will extract the key investor-relevant information, determine the market nuance, and synthesize it into the requested format. Without the article, a specific analysis is not possible.

---
ARTICLE TO ANALYZE:
---

[여기에 분석할 영어 뉴스 기사를 붙여넣으세요]"""),
            ],
            ),
            types.Content(
                role="model",
                parts=[
                    types.Part.from_text(text="""{"summary": "Understood. I am ready to analyze the provided news article."}"""),
                ],
            ),
            types.Content(
                role="user",
                parts=[
                    # 함수 인자로 받은 뉴스 기사를 여기에 입력
                    types.Part.from_text(text=article_text),
                ],
            ),
        ]
        
        # gemini 작동
        response_chunks = []
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
        ):
            response_chunks.append(chunk.text)
        time.sleep(5) #GEMINI 무료는 1분에 10번 호출 제한걸림
        
        return "".join(response_chunks)

    except Exception as e:
        print(f"An error occurred: {e}")
        return '{"summary": "Error during analysis."}'


# gemini API 실행
if __name__ == "__main__":

    df['summary'] = df['content'].apply(lambda content: analyze_news_article(content, api_key=API_KEY))

############################################3
# 4. 벡터화 (임베딩)

def get_summary_embedding(summary_text: str, client: genai.Client) -> list[float] | None:
    """
    하나의 요약본 텍스트를 받아 임베딩 벡터를 반환하는 함수.
    """
    # 내용이 비어있는지 확인
    if not summary_text or pd.isna(summary_text):
        return None
    
    try:
        # 'contents'가 아닌 'content' 파라미터로 단일 텍스트를 전달
        result = client.models.embed_content(
            model="models/text-embedding-004",
            contents=summary_text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        # 결과 객체에서 .embedding 속성으로 벡터를 직접 반환
        vectors = [obj.values for obj in result.embeddings]
        vectors=vectors[0]

        return vectors
    
    except Exception as e:
        print(f"API Error embedding '{summary_text[:50]}...': {e}")
        return None


# 임베딩 함수 실행
if __name__ == "__main__":
    # 클라이언트는 한 번만 생성합니다.
    client = genai.Client(api_key=API_KEY)
    df['embedding'] = df['summary'].apply(lambda text: get_summary_embedding(text, client))

#################################################3
# 6. Supabase 데이터베이스에 업로드

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

#저장에 사용할 데이터프레임
df=df[["title","publish_date","url","summary","embedding"]]

try:
    supabase: Client = create_client(supabase_url, supabase_key)
    print("Supabase에 연결하여 기존 데이터를 확인합니다.")

    # DB에 저장된 모든 'title' 목록을 가져오기
    response = supabase.table('financial_news_summary').select('title').execute()
    existing_titles = {item['title'] for item in response.data}
    print(f"현재 DB에 {len(existing_titles)}개의 기사가 있습니다.")

    # 새로 생성된 DataFrame에서 이미 있는 title들을 제외
    new_articles_df = df[~df['title'].isin(existing_titles)]

    if new_articles_df.empty:
        print("✅ 추가할 새로운 기사가 없습니다.")
    else:
        print(f"✨ {len(new_articles_df)}개의 새로운 기사를 찾았습니다. 업로드를 준비합니다.")

    
        # 업로드 형식으로 변환
        records_to_upload = new_articles_df.to_dict('records')
        # for record in records_to_upload:
        #     record['publish_date'] = record['publish_date'].isoformat()
        
        # 데이터 삽입
        data, count = supabase.table('financial_news_summary').insert(records_to_upload).execute()
        print(f"🎉 성공적으로 {len(data[1])}개의 새 기사를 업로드했습니다.")

except Exception as e:
    print(f"❌ 작업 중 오류 발생: {e}")
    
