# 트렌드 예측 및 개인화 로드맵 프로젝트 핵심 요약

## 1. 🔍 핵심 목표 및 차별점: 후행 지표에서 선행 지표로

이 프로젝트의 근본적인 차별점은 일반 뉴스가 다루는 **후행 지표(Lagging Indicators)**를 넘어, 미래를 예측하는 **선행 행동 지표(Leading Indicators)**에 집중하는 것입니다.

|구분|일반 뉴스/AI 코치|저희 프로젝트|
|---|---|---|
|**측정 대상**|이미 발생한 사건 (뉴스, 기사)|**사람들의 행동**: 돈의 흐름, 시간 투자, 학습 수요|
|**주요 출력**|정보 (Information)|**기회(Opportunity)** = 세상의 요구 지도|
|**최종 가치**|단순 추천/정보 제공|**'트렌드-역량 피드백 루프'**를 통한 성장 동반자 역할|

## 2. 📈 트렌드 분석을 위한 데이터 전략

트렌드 분석의 정확도를 높이기 위해, 트렌드의 **경제적 잠재력, 기술적 생존력, 대중적 관심도**를 측정하는 3대 핵심 행동 지표를 수집합니다.

|분류|지표 (Feature)|수집 난이도|주요 수집 소스|
|---|---|---|---|
|**돈의 흐름**|**투자금 유입 증가율** (`funding_volume_growth`)|상 (유료/고급 크롤링)|스타트업 뉴스 매체, 크라우드 펀딩 플랫폼, KVIC 보고서|
|**혁신의 흐름**|**특허 출원 증가율** (`patent_filing_rate`)|중 (정기적 크롤링)|KIPRIS (특허정보넷), USPTO|
|**역량의 흐름**|**학습 콘텐츠 수요 증가율** (`learning_demand_growth`)|하 (공개 API/크롤링)|Udemy, 인프런, K-MOOC 등 온라인 학습 플랫폼|
|**수요 포착**|**검색량 증가율** (`search_volume_growth`)|하 (공개 API)|Google Trends, Naver 데이터랩|
|**안정성 측정**|**정책/규제 변화 빈도** (`policy_change_frequency`)|중 (공공기관 웹사이트)|정부기관/국회 법안 관련 발표 및 보도자료|

## 3. 👥 개인화 및 데이터 모델링 (ERD)

개인화 서비스는 사용자가 오래 사용하지 않아도 **초기 '대리 데이터'**를 통해 즉시 가치를 제공하며, 사용자의 행동을 기록하여 로드맵을 정교화합니다.

### A. 데이터베이스 엔티티 (핵심 2가지 테이블)

1. **`EXTERNAL_TREND_DATA` (외부 트렌드 데이터):**
    
    - **컬럼 예시:** `trend_id` (PK), `trend_name`, `velocity_score` (계산된 최종 점수), `opportunity_level`, `search_volume_growth`, `funding_volume_growth` 등 **선행 지표 원본 데이터**를 저장합니다.
        
2. **`USER_PROFILE` (사용자 프로파일):**
    
    - **정적 프로파일 (Cold Start):** `aptitude_style` (성향), `initial_skill_map` (초기 역량), `interest_keywords` (관심 키워드)
        
    - **동적 프로파일 (행동 기록):** `roadmap_progress_rate` (진도율), `completed_skill_set` (획득 역량), `trend_engagement_log` (트렌드 클릭 기록), `ai_coach_complexity` (질문 복잡도)
        

### B. 개인화의 완성: 피드백 루프

사용자의 **로드맵 실행 데이터**와 **트렌드 탐색 기록**을 수집하여 AI 코치가 **'나의 잠재력'** 프로파일을 지속적으로 업데이트하고, 변화하는 **'세상의 요구 지도'**에 맞춰 개인화된 로드맵을 **실시간으로 재조정**하는 것이 가장 큰 차별점입니다.

## 4. 🧠 머신러닝 학습 피처

트렌드 속도계의 **미래 예측 모델**을 학습시키는 데 가장 중요한 피처는 **'시간 지연(Time Lag)'**을 적용한 **선행 지표**입니다.

- **핵심 피처 (입력 X):** `Funding_Volume_Growth_Pct`, `Patent_Filing_Rate_Pct`, `Learning_Demand_Growth_Pct`, `Search_Growth_Rate_Pct`, `Policy_Change_Freq_Count` 등 5가지 지표의 **과거 N주 데이터**.
    
- **타겟 피처 (정답 Y):** `Future_Velocity_Change_Pct` (예: 4주 후 트렌드 속도계 점수의 예상 변화율).
    

이러한 구조를 통해, 저희 프로젝트는 단순히 정보를 나열하는 것이 아니라 **개인의 성공 확률을 높이는 전략적 통찰력**을 제공할 것입니다.

