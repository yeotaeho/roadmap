# 📈 데이터 전략: 선행 지표 수집 및 Y값 계산 로직

## 1. 핵심 전략: 선행 지표 중심

### 1.1. 후행 지표 vs 선행 지표

| 구분 | 후행 지표 (일반 뉴스) | 선행 지표 (본 프로젝트) |
|------|---------------------|----------------------|
| **측정 대상** | 이미 발생한 사건 (뉴스, 기사) | **사람들의 행동**: 돈의 흐름, 시간 투자, 학습 수요 |
| **주요 출력** | 정보 (Information) | **기회(Opportunity)** = 세상의 요구 지도 |
| **예측력** | 낮음 (과거 사건 설명) | 높음 (미래 트렌드 예측) |

### 1.2. 5대 선행 지표

| 지표 분류 | 데이터 소스 (API/RSS) | 분석 의미 | 수집 난이도 |
|----------|---------------------|----------|------------|
| **돈의 흐름** | THE VC, 벤처투자종합포털, 스타트업 뉴스 | 투자금 유입 및 시장의 경제적 선택 | 상 |
| **혁신의 흐름** | KIPRIS(특허청), USPTO API | 기술적 생존력 및 미래 산업의 기초 | 중 |
| **역량의 흐름** | Google Trends, 인프런/Udemy 랭킹, 도서 API | 사람들의 시간 투자 및 학습 수요 증가율 | 하 |
| **수요 포착** | Google Trends, Naver 데이터랩 | 검색량 증가율로 대중 관심도 측정 | 하 |
| **거시/정책** | 한국은행(ECOS), FRED API, 정부 부처 RSS | 환경적 안정성 및 정책적 지원 방향 | 중 |

## 2. 데이터 수집 전략

### 2.1. 돈의 흐름 (Funding Flow)

**데이터 소스**:
- THE VC API
- 벤처투자종합포털 크롤링
- 스타트업 뉴스 RSS

**계산 방법**:
```python
funding_volume_growth = (
    (current_month_funding - previous_month_funding) 
    / previous_month_funding 
    * 100
)
```

**활용**:
- 트렌드의 경제적 잠재력 측정
- 시장의 실제 선택 반영

### 2.2. 혁신의 흐름 (Innovation Flow)

**데이터 소스**:
- KIPRIS (특허정보넷) API
- USPTO (미국 특허청) API

**계산 방법**:
```python
patent_filing_rate = (
    (current_quarter_patents - previous_quarter_patents)
    / previous_quarter_patents
    * 100
)
```

**활용**:
- 기술적 생존력 측정
- 미래 산업의 기초 파악

### 2.3. 역량의 흐름 (Competency Flow)

**데이터 소스**:
- Google Trends API
- 인프런/Udemy 랭킹 크롤링
- 도서 API (교보문고, YES24)

**계산 방법**:
```python
learning_demand_growth = (
    (current_month_course_enrollments - previous_month_enrollments)
    / previous_month_enrollments
    * 100
)
```

**활용**:
- 사람들의 실제 학습 수요 파악
- 역량 개발 방향성 제시

### 2.4. 수요 포착 (Demand Capture)

**데이터 소스**:
- Google Trends API
- Naver 데이터랩 API

**계산 방법**:
```python
search_volume_growth = (
    (current_week_searches - previous_week_searches)
    / previous_week_searches
    * 100
)
```

**활용**:
- 대중 관심도 측정
- 트렌드 속도계 지표로 활용

### 2.5. 거시/정책 (Macro/Policy)

**데이터 소스**:
- 한국은행 ECOS API
- FRED (Federal Reserve Economic Data) API
- 정부 부처 RSS

**계산 방법**:
```python
policy_change_frequency = count_of_policy_changes_in_period
```

**활용**:
- 환경적 안정성 측정
- 정책적 지원 방향 파악

## 3. Velocity Score 계산 로직

### 3.1. 개별 지표 정규화

각 지표를 0~1 범위로 정규화:

```python
def normalize_score(value, min_value, max_value):
    """지표를 0~1 범위로 정규화"""
    if max_value == min_value:
        return 0.5
    return (value - min_value) / (max_value - min_value)
```

### 3.2. 가중치 적용

각 지표에 가중치를 적용하여 종합 점수 계산:

```python
velocity_score = (
    funding_volume_growth_normalized * 0.3 +      # 돈의 흐름 (30%)
    patent_filing_rate_normalized * 0.2 +         # 혁신의 흐름 (20%)
    learning_demand_growth_normalized * 0.25 +    # 역량의 흐름 (25%)
    search_volume_growth_normalized * 0.15 +       # 수요 포착 (15%)
    policy_change_frequency_normalized * 0.1       # 거시/정책 (10%)
)
```

### 3.3. Opportunity Level 계산

Velocity Score를 기반으로 기회 수준 결정:

```python
def calculate_opportunity_level(velocity_score):
    """Velocity Score를 기반으로 기회 수준 계산 (1~5)"""
    if velocity_score >= 0.8:
        return 5  # 매우 높은 기회
    elif velocity_score >= 0.6:
        return 4  # 높은 기회
    elif velocity_score >= 0.4:
        return 3  # 보통 기회
    elif velocity_score >= 0.2:
        return 2  # 낮은 기회
    else:
        return 1  # 매우 낮은 기회
```

## 4. Y값 (Target) 계산 로직

### 4.1. 학습 데이터 구성

**Input (X)**: 현재 시점(t) 기준 과거 4주간의 5대 지표 데이터 시퀀스

```python
X = [
    [funding_1, patent_1, learning_1, search_1, policy_1],  # Week t-4
    [funding_2, patent_2, learning_2, search_2, policy_2],  # Week t-3
    [funding_3, patent_3, learning_3, search_3, policy_3],  # Week t-2
    [funding_4, patent_4, learning_4, search_4, policy_4],  # Week t-1
]
```

**Target (Y)**: 미래 4주 후의 실제 계산된 Velocity Score 변화량

```python
Y = velocity_score_at_t_plus_4 - velocity_score_at_t
```

### 4.2. 시계열 예측 모델

**모델 선택**:
- **GRU**: 시계열 데이터 학습에 적합
- **Time-Series Transformer**: 장기 의존성 학습에 우수

**Loss Function**: MSE (Mean Squared Error)

```python
loss = mean_squared_error(y_true, y_pred)
```

### 4.3. 예측 파이프라인

```python
def predict_future_velocity(current_trend_data):
    """
    현재 트렌드 데이터를 기반으로 미래 Velocity Score 예측
    
    Args:
        current_trend_data: 과거 4주간의 지표 데이터
        
    Returns:
        predicted_velocity_change: 예상 Velocity Score 변화량
    """
    # 1. 데이터 전처리 및 정규화
    normalized_data = normalize_features(current_trend_data)
    
    # 2. 시계열 모델로 예측
    predicted_change = gru_model.predict(normalized_data)
    
    # 3. 후처리 및 검증
    validated_prediction = validate_prediction(predicted_change)
    
    return validated_prediction
```

## 5. 데이터 수집 주기

### 5.1. 실시간 수집 (High Frequency)

- **검색량**: 일일 수집 (Google Trends, Naver 데이터랩)
- **학습 수요**: 주간 수집 (인프런, Udemy 랭킹)

### 5.2. 정기 수집 (Medium Frequency)

- **투자금**: 주간 수집 (THE VC, 벤처투자종합포털)
- **특허**: 월간 수집 (KIPRIS, USPTO)

### 5.3. 이벤트 기반 수집 (Low Frequency)

- **정책 변화**: 이벤트 발생 시 수집 (정부 부처 RSS)
- **거시 경제**: 월간 수집 (한국은행 ECOS, FRED)

## 6. 데이터 품질 관리

### 6.1. 데이터 검증

```python
def validate_data(data_point):
    """데이터 포인트 검증"""
    checks = [
        check_missing_values(data_point),
        check_outliers(data_point),
        check_temporal_consistency(data_point),
    ]
    return all(checks)
```

### 6.2. 이상치 처리

```python
def handle_outliers(data, method='iqr'):
    """이상치 처리"""
    if method == 'iqr':
        Q1 = data.quantile(0.25)
        Q3 = data.quantile(0.75)
        IQR = Q3 - Q1
        return data[(data >= Q1 - 1.5*IQR) & (data <= Q3 + 1.5*IQR)]
```

## 7. 피드백 루프

### 7.1. 예측 정확도 모니터링

```python
def calculate_prediction_accuracy(predictions, actuals):
    """예측 정확도 계산"""
    mse = mean_squared_error(actuals, predictions)
    mae = mean_absolute_error(actuals, predictions)
    return {'mse': mse, 'mae': mae}
```

### 7.2. 모델 재학습 트리거

- 주간 예측 정확도가 임계값 이하로 떨어질 때
- 새로운 데이터 패턴이 감지될 때
- 월간 정기 재학습

## 8. 향후 개선 계획

1. **실시간 스트리밍**: Apache Kafka를 통한 실시간 데이터 수집
2. **자동화된 피처 엔지니어링**: AutoML 도구 활용
3. **앙상블 모델**: 여러 모델의 예측을 결합하여 정확도 향상
4. **도메인 특화 모델**: 분야별로 특화된 예측 모델 개발
