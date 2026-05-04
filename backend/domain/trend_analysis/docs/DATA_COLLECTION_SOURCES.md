# 🌍 글로벌 트렌드 분석 및 예측 엔진 데이터 수집 출처 상세 가이드

이 문서는 `Data_Collector` 노드가 처리할 수 있는 구체적인 데이터 출처를 URL과 함께 정리한 가이드입니다. 이는 **선행 지표(Leading Indicators)** 중심으로 구성되었으며, 4070 Super 환경에서 멀티모달 에이전트가 효율적으로 수집·처리할 수 있도록 무료/공개 API나 RSS 피드를 우선 고려했습니다.

## 📋 개요

각 카테고리별로:
- **수집 방법 제안**: Python 라이브러리(`requests`, `feedparser`, `BeautifulSoup`)를 사용해 크롤링하거나 API 호출. API 키가 필요한 경우 무료 티어 활용.
- **주의사항**: Rate Limit, API 약관 준수. 초기 MVP 구현 시 1~2개 출처부터 테스트.
- **형태**: 텍스트(뉴스/보고서) → `Issue_Analyst_NLP`로, 수치(투자액/검색량) → `Trend_Forecaster_TS`로 분기.

---

## 1. 💰 돈의 흐름 (Economic Flow) - "자본은 미래로 먼저 움직인다"

투자 동향을 통해 미래 트렌드를 예측. 주로 수치 데이터(투자액, 거래량)와 텍스트(투자 뉴스) 수집.

### Venture Capital (VC) 투자 데이터

스타트업 투자 라운드(시리즈 A/B 등)와 산업군별 추이.

- **Crunchbase**
  - 웹사이트: https://www.crunchbase.com/
  - API: https://www.crunchbase.com/developer/v4
  - 설명: 무료 키 발급 가능, 투자 이벤트 검색
  - 데이터 형태: 수치(투자액) + 텍스트(투자 뉴스)

- **The VC (한국 VC 포커스)**
  - 웹사이트: https://thevc.kr/
  - 투자 목록: https://thevc.kr/investments
  - 설명: RSS 없음, 웹 스크래핑 필요
  - 데이터 형태: 텍스트(투자 뉴스)

- **스타트업레시피 (한국 스타트업 뉴스)**
  - 웹사이트: https://startuprecipe.co.kr/
  - RSS 피드: https://startuprecipe.co.kr/feed
  - 설명: 투자 뉴스 피드
  - 데이터 형태: 텍스트(투자 뉴스)

### 글로벌 상장지수펀드(ETF) 자금 유입

테마별 ETF 거래량/자금 흐름 (e.g., AI ETF: ARKK).

- **Yahoo Finance**
  - 웹사이트: https://finance.yahoo.com/etfs
  - API 대안: `yfinance` 라이브러리 사용
  - 데이터 다운로드: https://finance.yahoo.com/quote/ARKK/history
  - 설명: 역사적 데이터 CSV 다운로드 가능
  - 데이터 형태: 수치(거래량, 자금 흐름)

### 정부 예산 편성

국가별 예산 배분 (e.g., R&D 투자).

- **기획재정부 (한국)**
  - 웹사이트: https://www.moef.go.kr/
  - 예산안 다운로드: https://www.moef.go.kr/nw/nes/detailNesDtaView.do?menuNo=4010100
  - 설명: PDF/Excel 보고서 다운로드
  - 데이터 형태: 수치(예산 배분)

- **미국 연방 예산**
  - 웹사이트: https://www.whitehouse.gov/omb/budget/
  - 데이터: https://www.whitehouse.gov/omb/historical-tables/
  - 설명: Excel 테이블 다운로드
  - 데이터 형태: 수치(예산 배분)

---

## 2. 💡 혁신의 흐름 (Innovation Flow) - "기술적 가능성을 엿보다"

기술적 움직임을 포착. 주로 텍스트(특허/논문 초록)와 수치(출원 수/인용 횟수).

### 특허 출원 데이터

키워드별 출원 추이 (e.g., "AI security" 특허 수).

- **KIPRIS (한국 특허)**
  - 웹사이트: http://www.kipris.or.kr/
  - KIPRIS Plus 포털: https://plus.kipris.or.kr/portal/data/util/DBII_000000000000001/view.do
  - API: http://www.kipris.or.kr/openapi/rest/patentInfoSearchService
  - 설명: 무료 API 키 발급 가능 (KIPRIS Plus 포털에서 발급), 환경변수 `KIPRIS_API_KEY`에 저장
  - 데이터 형태: 텍스트(특허 초록) + 수치(출원 수)
  - 활용: 키워드별 특허 출원 추이, 연도별/분기별 출원 수 시계열 데이터 추출

- **USPTO (미국 특허)**
  - 웹사이트: https://www.uspto.gov/
  - API: https://developer.uspto.gov/ds-api/
  - 설명: Patent Application Information Retrieval API
  - 데이터 형태: 텍스트(특허 초록) + 수치(출원 수)

- **Google Patents**
  - 웹사이트: https://patents.google.com/
  - API: 없음
  - 대안: https://developers.google.com/custom-search/v1 (커스텀 검색으로 대체)
  - 설명: 검색 API를 통한 간접 접근
  - 데이터 형태: 텍스트(특허 초록)

### 논문 초록 (Research Papers)

첨단 분야 논문 추이 (e.g., arXiv AI 카테고리).

- **arXiv**
  - 웹사이트: https://arxiv.org/
  - API: https://arxiv.org/help/api/user-manual
  - 예시 쿼리: https://export.arxiv.org/api/query?search_query=cat:cs.AI
  - 설명: 초록/메타데이터 쿼리 가능
  - 데이터 형태: 텍스트(논문 초록) + 수치(인용 횟수)

### 오픈소스 활동 (GitHub)

리포지토리 Star/Contributor 변화 (e.g., AI 라이브러리).

- **GitHub**
  - 웹사이트: https://github.com/
  - API: https://api.github.com/
  - 예시: https://api.github.com/repos/huggingface/transformers
  - 설명: REST API, Star 수 쿼리, 무료 사용 가능
  - 데이터 형태: 수치(Star 수, Contributor 수)

---

## 3. 👥 사람의 흐름 (Competency/Demand) - "대중의 관심과 학습 의지"

사람들의 관심과 수요. 주로 수치(검색량/강의 랭킹)와 텍스트(채용 요구사항).

### 검색 트렌드

키워드별 검색량 변화.

- **Google Trends**
  - 웹사이트: https://trends.google.com/
  - 라이브러리: `PyTrends` 사용
  - 데이터 다운로드: https://trends.google.com/trends/api/explore
  - 설명: JSON 형식 데이터 다운로드
  - 데이터 형태: 수치(검색량)

- **Naver DataLab**
  - 웹사이트: https://datalab.naver.com/
  - 트렌드 검색: https://datalab.naver.com/keyword/trendSearch.naver
  - 설명: API 없음, 웹에서 CSV 다운로드
  - 데이터 형태: 수치(검색량)

### 학습 수요 (Online Learning)

베스트셀러 강의 카테고리.

- **Udemy**
  - 웹사이트: https://www.udemy.com/
  - API: https://www.udemy.com/developers/affiliate/
  - 설명: Affiliate API, 강의 목록 쿼리
  - 데이터 형태: 수치(강의 랭킹)

- **Coursera**
  - 웹사이트: https://www.coursera.org/
  - RSS: https://www.coursera.org/sitemap~courses.xml
  - 설명: API 없음, 신규 강의 피드
  - 데이터 형태: 텍스트(강의 정보)

- **Inflearn (한국)**
  - 웹사이트: https://www.inflearn.com/
  - 베스트셀러: https://www.inflearn.com/courses
  - 설명: RSS 없음, 웹 스크래핑 필요
  - 데이터 형태: 수치(강의 랭킹)

### 채용 공고 (Job Market)

기술 스택 변화.

- **LinkedIn**
  - 웹사이트: https://www.linkedin.com/jobs/
  - API: https://developer.linkedin.com/docs/api/v2/jobs
  - 설명: Jobs API, 키워드 검색
  - 데이터 형태: 텍스트(채용 공고)

- **Wanted (한국)**
  - 웹사이트: https://www.wanted.co.kr/
  - RSS: https://www.wanted.co.kr/wdlist/rss
  - 설명: 채용 RSS 피드
  - 데이터 형태: 텍스트(채용 공고)

- **Saramin (한국)**
  - 웹사이트: https://www.saramin.co.kr/
  - API: https://www.saramin.co.kr/zf_user/help/api
  - 설명: 개발자 API, 채용 데이터 쿼리
  - 데이터 형태: 텍스트(채용 공고)

---

## 4. 📰 담론의 흐름 (Discourse Flow) - "현재 이슈와 리스크"

현재 이슈와 반응. 주로 텍스트(뉴스/댓글)로 감성 분석.

### 글로벌 뉴스 RSS

헤드라인/본문.

- **Reuters**
  - 웹사이트: https://www.reuters.com/
  - RSS: https://www.reuters.com/tools/rss
  - 예시 피드: https://www.reuters.com/arc/outboundfeeds/technology/feed/
  - 설명: 카테고리별 피드 제공
  - 데이터 형태: 텍스트(뉴스 헤드라인/본문)

- **Bloomberg**
  - 웹사이트: https://www.bloomberg.com/
  - RSS: https://www.bloomberg.com/feeds/technology.xml
  - 설명: 기술 섹션 피드
  - 데이터 형태: 텍스트(뉴스 헤드라인/본문)

- **TechCrunch**
  - 웹사이트: https://techcrunch.com/
  - RSS: https://techcrunch.com/feed/
  - 설명: 전체 피드
  - 데이터 형태: 텍스트(뉴스 헤드라인/본문)

### 커뮤니티 및 SNS

실시간 감성.

- **Reddit**
  - 웹사이트: https://www.reddit.com/
  - RSS: https://www.reddit.com/r/technology/.rss
  - API: https://www.reddit.com/dev/api
  - 설명: 서브레딧 피드
  - 데이터 형태: 텍스트(게시글/댓글)

- **X (Twitter)**
  - 웹사이트: https://x.com/
  - API: https://developer.x.com/en/docs/twitter-api
  - 설명: Posts 검색 API, 무료 티어 제한적
  - 데이터 형태: 텍스트(트윗)

- **YouTube**
  - 웹사이트: https://www.youtube.com/
  - API: https://developers.google.com/youtube/v3
  - 설명: 댓글/비디오 메타데이터 쿼리
  - 데이터 형태: 텍스트(댓글) + 멀티모달(썸네일)

### 싱크탱크 보고서

정기 리포트 요약.

- **Gartner**
  - 웹사이트: https://www.gartner.com/
  - RSS: https://www.gartner.com/en/newsroom/rss
  - 보고서: https://www.gartner.com/en/information-technology/insights
  - 설명: 뉴스룸 피드, 보고서 다운로드
  - 데이터 형태: 텍스트(보고서 요약)

- **McKinsey**
  - 웹사이트: https://www.mckinsey.com/
  - RSS: https://www.mckinsey.com/featured-insights/rss
  - 보고서: https://www.mckinsey.com/featured-insights
  - 설명: 인사이트 피드, 보고서 다운로드
  - 데이터 형태: 텍스트(보고서 요약)

---

## 🛠️ 구현 팁: `Data_Collector` 노드에서 출처 활용

### 텍스트 데이터 처리

RSS/웹 스크래핑 → `feedparser`로 피드 파싱, `BeautifulSoup`로 본문 추출.

```python
import feedparser
from bs4 import BeautifulSoup
import requests

# RSS 피드 파싱
feed = feedparser.parse('https://techcrunch.com/feed/')
for entry in feed.entries:
    title = entry.title
    link = entry.link
    # 본문 추출
    response = requests.get(link)
    soup = BeautifulSoup(response.content, 'html.parser')
    content = soup.get_text()
```

### 수치 데이터 처리

API 호출 → JSON 파싱 후 Pandas로 시계열 변환.

```python
import requests
import pandas as pd
import yfinance as yf
import os
from dotenv import load_dotenv

# Yahoo Finance 예시
ticker = yf.Ticker("ARKK")
hist = ticker.history(period="1y")
# 시계열 데이터로 변환

# KIPRIS API 예시
load_dotenv()
KIPRIS_API_KEY = os.getenv('KIPRIS_API_KEY')
KIPRIS_API_URL = os.getenv('KIPRIS_API_URL', 'http://www.kipris.or.kr/openapi/rest')

# 특허 출원 검색
params = {
    'accessKey': KIPRIS_API_KEY,
    'word': '인공지능',  # 검색 키워드
    'numOfRows': 100
}
response = requests.get(f'{KIPRIS_API_URL}/patentInfoSearchService', params=params)
data = response.json()

# 시계열 데이터로 변환 (연도별 출원 수 집계)
df = pd.DataFrame(data['items'])
df['출원일'] = pd.to_datetime(df['출원일'])
df['연도'] = df['출원일'].dt.year
yearly_counts = df.groupby('연도').size()
```

### 멀티모달 처리

이미지/비디오 포함 시 (e.g., YouTube 썸네일), 별도 다운로드 후 로컬 저장.

```python
import requests
from pathlib import Path

def download_image(url, save_path):
    response = requests.get(url)
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, 'wb') as f:
        f.write(response.content)
```

### API 키 관리

환경변수로 API 키 관리 (`.env` 파일 사용).

```python
# .env 파일 예시
# KIPRIS API 설정
KIPRIS_API_KEY=your_api_key_here
KIPRIS_API_URL=http://www.kipris.or.kr/openapi/rest
KIPRIS_REQUEST_LIMIT=1000

# 사용 예시
import os
from dotenv import load_dotenv

load_dotenv()
KIPRIS_API_KEY = os.getenv('KIPRIS_API_KEY')
KIPRIS_API_URL = os.getenv('KIPRIS_API_URL', 'http://www.kipris.or.kr/openapi/rest')
```

### 스케줄링

Crontab 또는 APScheduler로 매일 실행.

```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()
scheduler.add_job(data_collector_job, 'cron', hour=3, minute=0)
scheduler.start()
```

### 초기 테스트 전략

IT/과학 분야부터 시작하세요. 예: Google Trends (https://trends.google.com/) + TechCrunch RSS (https://techcrunch.com/feed/)로 MVP 구축.

---

## 📝 참고사항

- **Rate Limit**: 각 API의 Rate Limit을 확인하고, 필요시 백오프 전략 구현
- **API 약관 준수**: 각 서비스의 이용약관을 확인하고 준수
- **데이터 중복 방지**: 날짜+소스 기준으로 중복 수집 방지 로직 구현
- **에러 처리**: 네트워크 오류, API 오류 등에 대한 재시도 로직 구현

특정 산업 (e.g., AI, 바이오)에 초점을 맞추고 싶으시면, 그 분야에 최적화된 추가 출처를 더 제안해 드릴 수 있습니다.

