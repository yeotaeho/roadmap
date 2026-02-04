# 🤖 AI 에이전트 아키텍처 (LangGraph 기반)

## 1. 개요

RTX 4070 Super(12GB) 환경과 **LangGraph**를 활용한 **스타 토폴로지(Star Topology, Orchestrator-Worker 패턴)** 구조는 현재 프로젝트 규모와 복잡도를 고려할 때 매우 탁월하고 적합한 선택입니다.

단순한 챗봇이 아니라, 사용자의 의도에 따라 **DB를 수정**하거나 **트렌드 데이터를 조회**하고 **개인화된 로드맵을 생성**해야 하므로, 상태(State)를 관리하고 노드 간의 흐름을 제어하는 오케스트레이터가 필수적입니다.

## 2. 스타 토폴로지 기반 에이전트 구조

### 2.1. 구조 개요

이 구조의 핵심은 **오케스트레이터(Orchestrator)**가 사용자의 입력을 분석하여 적절한 **전문가 노드(Worker Nodes)**에게 업무를 배정하고, 그 결과를 취합하여 사용자에게 최종 응답을 하는 것입니다.

**가이드형 온보딩(Guided Onboarding)**을 위해 **`Interview_Lead` 노드**가 추가되어, 에이전트가 먼저 손을 내밀고 대화를 리드합니다. "무엇이든 물어보세요"라는 빈 검색창보다 훨씬 친절하고 효과적인 사용자 경험을 제공합니다.

### 2.2. 워크플로우 구성도

```
┌─────────────────┐
│  Start (Agent)  │
│  첫 접속         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Interview_Lead  │ ◄─── 가이드형 온보딩 (에이전트 주도)
│  (온보딩 노드)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  User Response  │
│  (사용자 답변)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orchestrator   │ ◄─── 의도 분석 및 라우팅
│  (Router Node)  │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┬──────────┐
    │         │          │          │          │
    ▼         ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Profile │ │ Trend  │ │Insight │ │Interview│ │Answer  │
│Manager │ │Analyst │ │ Coach  │ │  Lead   │ │ Node   │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
    │         │          │          │          │
    │         │          │          │          │
    └─────────┴──────────┴──────────┴──────────┘
                    │
                    ▼
            ┌───────────────┐
            │ Final Response│
            │   (출력)      │
            └───────────────┘
```

### 2.3. 워크플로우 단계

1. **Start (Agent)**: `Interview_Lead` 노드가 첫 질문을 던지며 시작 (가이드형 온보딩)
2. **User Input**: 사용자가 답변을 입력
3. **Orchestrator (Router Node)**: LLM이 사용자의 의도(Intent)와 상태를 분석하여 분기
   - *"사용자가 질문에 대답했는가?"* → `Profile_Manager`로 보내서 데이터 추출
   - *"정보가 더 필요한가?"* → `Interview_Lead`로 보내서 다음 질문 생성
   - *"세상 흐름/트렌드가 궁금한가?"* → `Trend_Analyst`
   - *"나의 진로 상담/로드맵이 필요한가?"* → `Insight_Coach`
4. **Worker Nodes (전문가 노드)**:
   - **`Interview_Lead`**: 상태 체크 후 다음 질문 생성 (가이드형 온보딩)
   - **`Profile_Manager`**: 대화에서 정보(스킬, 관심사 등)를 추출하여 **DB(`users`, `user_competency`)에 저장**
   - **`Trend_Analyst`**: DB의 **`external_trend_data`**를 조회하여 현재 지표 설명
   - **`Insight_Coach`**: 사용자 정보 + 트렌드 데이터를 결합하여 **로드맵 생성**
5. **Review & Answer**: 오케스트레이터가 검토 후 최종 응답 생성

## 3. LangGraph 노드 정의 및 역할

| 노드 명칭 | 베이스 모델 | 주요 역할 | 튜닝 여부 | 세부 동작 |
|----------|------------|----------|----------|----------|
| **Interview_Lead** | Llama-3.1-8B-Korean-Bllossom (Local) | **가이드형 온보딩 (에이전트 주도)** | O (선택적 - Persona Tuning) | 상태 체크 후 미확인 필수 정보에 대한 자연스러운 질문 생성 및 대화 리드 |
| **Orchestrator** | Llama-3.1-70B (Groq) | **의도 분석 및 라우팅** | X (Few-Shot Prompting) | 사용자의 답변을 보고 다음 단계 결정, 워커 노드 결과 검증 |
| **Profile_Manager** | Llama-3.1-8B-Korean-Bllossom (Local) | **데이터 추출 및 저장** | O (필수 - QLoRA) | 대화에서 정확하게 키워드와 수치를 추출하여 JSON/SQL 형식으로 변환 |
| **Trend_Analyst** | Llama-3.1-8B-Korean-Bllossom (Local) 또는 70B (Groq) | **통계 기반 정보 제공** | O (QLoRA - Text-to-SQL) | 자연어 질문을 SQL로 변환하여 실시간 지표 조회 및 해석 |
| **Insight_Coach** | Llama-3.1-70B (Groq) | **개인화 전략 수립** | X (RAG 기반) | 사용자 역량과 트렌드 요구 스펙 비교하여 역량 갭 분석 및 로드맵 생성 |
| **Answer_Node** | Llama-3.1-8B-Korean-Bllossom (Local) | **최종 응답 생성** | X (Prompting) | 각 노드 결과를 취합하여 친절하고 명확한 대화문으로 정리 |

## 4. 이 구조가 프로젝트에 적합한 이유

### 4.1. 복잡한 상태 관리 (LangGraph의 강점)

- 사용자가 "아까 말한 코딩 스킬 3점으로 수정해줘"라고 할 때, 이전 대화 맥락과 DB 상태를 유지하며 처리하기에 LangGraph가 최적입니다.
- `TypedDict`를 사용하여 사용자의 의도, 추출된 데이터, 이전 대화 기록을 전역 상태로 유지합니다.

### 4.2. RTX 4070 Super(12GB) 최적화

- 여러 모델을 동시에 띄우는 대신, **하나의 강력한 Llama-3.1-8B 모델**에게 각 노드별로 다른 **System Prompt(역할)**를 부여하여 실행할 수 있습니다.
- 12GB VRAM 안에서 충분히 매끄럽게 돌아갑니다.

### 4.3. 확장성

- 나중에 "도서 추천 노드"나 "뉴스 요약 노드"를 추가하고 싶을 때, 스타 토폴로지 구조에서는 새로운 노드만 하나 더 붙이면 되므로 유지보수가 매우 쉽습니다.

## 5. 상태(State) 관리

### 5.1. State 정의

```python
from typing import TypedDict, List, Optional
from typing_extensions import Annotated
import operator

class AgentState(TypedDict):
    """에이전트의 전역 상태"""
    messages: Annotated[List[str], operator.add]  # 대화 기록
    user_id: Optional[int]                         # 사용자 ID
    workflow_stage: Optional[str]                  # 현재 대화 단계 (icebreaking | interest_exploration | competency_assessment | value_deepening | complete)
    intent: Optional[str]                          # 의도 (Profile_Update | Trend_Search | Career_Advice | Need_More_Info)
    extracted_data: Optional[dict]                 # 추출된 데이터 (스킬, 관심사 등)
    trend_data: Optional[dict]                     # 트렌드 조회 결과
    insight: Optional[str]                         # 생성된 인사이트
    profile_completeness: Optional[dict]           # 프로필 완성도 정보
    final_response: Optional[str]                  # 최종 응답
```

### 5.2. 상태 전달 흐름

각 노드는 State를 받아서 처리하고, 업데이트된 State를 반환합니다. LangGraph가 자동으로 상태를 병합하고 다음 노드로 전달합니다.

## 6. 노드별 상세 설계

### 6.1. 👑 Orchestrator Node (The Brain)

**베이스 모델**: **Llama-3.1-70B (Groq)**

**역할**:
- **판단**: 사용자의 답변을 보고 다음 단계(데이터 추출/추가 질문/분석 시작) 결정
- **검증**: 워커 노드들이 뽑아온 데이터가 논리적으로 타당한지 최종 검토
- **라우팅**: 의도에 따라 적절한 노드로 분기

**튜닝 여부**: **X (Few-Shot Prompting)**
- 70B 모델은 지시 이행 능력이 탁월하므로, 분기 조건(Condition)과 검증 규칙을 담은 정교한 프롬프트면 충분합니다.
- Groq API를 사용하므로 로컬 VRAM 소모 없음

**필요 데이터**:
- 전체 대화 이력 (`AgentState.messages`)
- DB 스키마 정의서
- 노드 간 전환 규칙(State Machine)

**System Prompt 예시**:
```
당신은 사용자의 의도를 분석하고 워크플로우를 제어하는 오케스트레이터입니다.

사용자의 메시지와 현재 상태를 분석하여 다음 중 하나로 분류하세요:

1. Profile_Update: 사용자가 자신의 정보(스킬, 관심사 등)를 업데이트하려는 경우
2. Trend_Search: 사용자가 트렌드나 세상 흐름에 대해 물어보는 경우
3. Career_Advice: 사용자가 진로 상담이나 로드맵을 요청하는 경우
4. Need_More_Info: 프로필이 불완전하여 추가 정보가 필요한 경우

각 노드에서 반환된 데이터의 논리적 타당성도 검증하세요.
```

**조건부 엣지(Conditional Edge)**:
```python
async def route_intent(state: AgentState) -> str:
    """의도와 상태에 따라 다음 노드 결정"""
    intent = state.get("intent")
    user_id = state.get("user_id")
    
    # 프로필 완성도 체크
    if user_id:
        completeness = await check_user_profile_completeness(user_id)
        
        # 프로필이 불완전하고 사용자가 질문에 답변 중이면 Interview_Lead로
        if not completeness["is_complete"] and intent == "Profile_Update":
            return "interview_lead"
    
    # 의도에 따른 라우팅
    if intent == "Profile_Update":
        return "profile_manager"
    elif intent == "Trend_Search":
        return "trend_analyst"
    elif intent == "Career_Advice":
        return "insight_coach"
    elif intent == "Need_More_Info":
        return "interview_lead"  # 추가 정보 필요 시
    else:
        return "answer_node"  # 불명확한 경우 재질문
```

### 6.2. 🎤 Interview_Lead Node (The Guide) - 가이드형 온보딩

**역할**: 에이전트가 먼저 손을 내밀고 대화를 리드하는 가이드형 온보딩

**핵심 가치**:
- "무엇이든 물어보세요"라는 빈 검색창보다, **AI가 먼저 손을 내밀고 대화를 리드**
- 사용자의 상태(이미 얻은 정보와 아직 얻지 못한 정보)를 체크하고 다음 질문을 던짐
- 선택 장애 해소 및 서비스 진입 장벽 낮춤

**주요 기능**:
1. **상태 체크**: `AgentState`를 보고 아직 수집되지 않은 스키마 항목 파악
   - `pref_domain_json` (관심 도메인)
   - `user_competency` (현재 역량)
   - `value_score` (가치관)
2. **질문 생성**: 딱딱한 설문이 아니라 대화의 맥락에 맞는 부드러운 질문 생성
3. **주도권 유지**: 사용자가 딴길로 새면 다시 주제로 돌아오게 하거나, 답변에 공감하며 다음 단계로 유도

**단계별 대화 가이드 (Workflow Stage)**:

| 단계 | 목표 | 에이전트의 첫 질문(예시) |
|------|------|------------------------|
| **Stage 1: 아이스브레이킹** | 가벼운 인사 및 서비스 가치 전달 | "반가워요! 요즘 세상이 참 빨리 변하죠? 혹시 뉴스나 유튜브 보면서 '나도 저런 거 해보고 싶다'고 생각했던 게 있나요?" |
| **Stage 2: 관심사 탐색** | `pref_domain_json` 채우기 | "오, AI 아트를 보셨군요! 기술적인 부분보다는 창의적인 결과물에 더 끌리시는 편인가요?" |
| **Stage 3: 역량 파악** | `user_competency` 채우기 | "관심사는 확실하시네요! 그럼 혹시 그 꿈을 위해 지금 바로 시작할 수 있는 자신만의 무기(스킬)가 있다면 무엇일까요?" |
| **Stage 4: 가치관 심화** | `value_score` 분석 | "좋아요. 그럼 나중에 그 일을 할 때, 연봉이 높은 게 중요할까요, 아니면 내 이름으로 된 멋진 작품을 남기는 게 더 중요할까요?" |

**System Prompt 예시**:
```
당신은 따뜻하고 유능한 커리어 멘토입니다. 사용자가 막막해하지 않도록 선택지를 주거나 예시를 들어주며 대화를 이끌어주세요.

현재 대화 단계: {current_stage}
이미 수집된 정보: {collected_data}
아직 수집되지 않은 정보: {missing_data}

사용자의 이전 답변을 존중하며, 자연스럽게 다음 질문으로 이어가세요.
```

**Tool 정의**:
```python
@tool
async def check_user_profile_completeness(user_id: int) -> dict:
    """사용자 프로필 완성도 체크"""
    async with AsyncSessionLocal() as session:
        user = await session.query(User).filter(User.id == user_id).first()
        competencies = await session.query(UserCompetency).filter(
            UserCompetency.user_id == user_id
        ).all()
        
        missing_fields = []
        
        # 관심사 체크
        if not user.pref_domain_json or not user.pref_domain_json.get("interests"):
            missing_fields.append("interests")
        
        # 역량 체크
        if not competencies:
            missing_fields.append("competencies")
        
        # 가치관 체크
        if user.value_growth is None or user.value_stability is None:
            missing_fields.append("values")
        
        return {
            "is_complete": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "completion_rate": (4 - len(missing_fields)) / 4 * 100
        }
```

**베이스 모델**: **Llama-3.1-8B-Korean-Bllossom (Local)**

**역할**:
- **주도권 유지**: 사용자가 대화에 몰입하도록 질문을 던지고 공감함
- **결측치 파악**: 아직 채워지지 않은 사용자 정보(관심사, 스킬 등)를 기반으로 질문 생성
- **대화 리드**: 사용자가 딴길로 새면 다시 주제로 돌아오게 하거나, 답변에 공감하며 다음 단계로 유도

**튜닝 여부**: **O (선택적 - Persona Tuning)**
- 따뜻하고 전문적인 '커리어 멘토'의 말투를 유지하도록 튜닝하거나, 강력한 시스템 프롬프트를 적용합니다.
- QLoRA로 Persona 특화 튜닝 가능 (선택사항)

**필요 데이터**:
- 사용자 프로필 현황(JSON) - `check_user_profile_completeness` Tool
- 페르소나 가이드라인
- 대화 유도 스크립트 예시

**구현 전략**:
- **로컬 모델 사용**: 8B 모델을 QLoRA(4-bit)로 로드하여 VRAM 효율적 사용
- **프롬프트 전략**: "페르소나 부여" - 따뜻하고 유능한 커리어 멘토 역할
- **데이터 연동**: 스키마에 저장된 `users` 테이블의 빈 컬럼들을 실시간으로 체크하는 Tool과 연결

**에이전트가 던질 역사적인 첫 번째 질문**:
```
"안녕하세요! 세상은 빠르게 변하는데 나만 멈춰있는 기분이 들 때가 있죠? 
제가 당신의 숨은 잠재력을 찾아 미래의 파도에 올라타게 도와드릴게요. 
요즘 가장 흥미롭게 보고 있는 세상의 변화가 있나요?"
```

이 첫 질문을 시작으로, 사용자의 답변에서 데이터를 뽑아내는 **Profile_Manager용 학습 데이터셋 구성**이 중요합니다.

**심리적 효과**:
1. **선택 장애 해소**: 무엇을 물어볼지 고민할 필요 없이 답변만 하면 됨
2. **개인화된 경험**: "나에게 집중하고 있구나"라는 느낌으로 서비스 충성도 향상
3. **데이터 품질 향상**: 에이전트가 의도한 방향으로 질문을 던지기 때문에 양질의 데이터 확보

### 6.2. Orchestrator Node (라우터)

**역할**: 사용자 메시지에서 의도를 파악하고 적절한 노드로 라우팅

**System Prompt 예시**:
```
당신은 사용자의 의도를 분석하는 라우터입니다. 사용자의 메시지를 분석하여 다음 중 하나로 분류하세요:

1. Profile_Update: 사용자가 자신의 정보(스킬, 관심사 등)를 업데이트하려는 경우
2. Trend_Search: 사용자가 트렌드나 세상 흐름에 대해 물어보는 경우
3. Career_Advice: 사용자가 진로 상담이나 로드맵을 요청하는 경우

의도만 반환하세요 (예: "Profile_Update")
```

**조건부 엣지(Conditional Edge)**:
```python
async def route_intent(state: AgentState) -> str:
    """의도와 상태에 따라 다음 노드 결정"""
    intent = state.get("intent")
    user_id = state.get("user_id")
    
    # 프로필 완성도 체크
    if user_id:
        completeness = await check_user_profile_completeness(user_id)
        
        # 프로필이 불완전하고 사용자가 질문에 답변 중이면 Interview_Lead로
        if not completeness["is_complete"] and intent == "Profile_Update":
            return "interview_lead"
    
    # 의도에 따른 라우팅
    if intent == "Profile_Update":
        return "profile_manager"
    elif intent == "Trend_Search":
        return "trend_analyst"
    elif intent == "Career_Advice":
        return "insight_coach"
    elif intent == "Need_More_Info":
        return "interview_lead"  # 추가 정보 필요 시
    else:
        return "answer_node"  # 불명확한 경우 재질문
```

### 6.3. ✍️ Profile_Manager Node (The Scribe)

**베이스 모델**: **Llama-3.1-8B-Korean-Bllossom (Local)**

**역할**:
- **비정형 데이터의 정형화**: 대화 속에서 "코딩은 3점 정도", "경제에 관심 많아" 같은 정보를 추출하여 DB 컬럼에 맞게 변환
- **데이터 추출 및 저장**: LLM이 대화에서 JSON 구조를 추출하고, 이를 DB에 `INSERT/UPDATE`

**튜닝 여부**: **O (필수 - QLoRA)**
- 대화에서 정확하게 특정 키워드와 수치를 뽑아내어 JSON/SQL 형식으로 출력하도록 학습해야 합니다.
- **Hallucination 방지**가 핵심: 사용자가 아무리 횡설수설해도 에이전트가 "아, 이 사람은 IT에 관심이 있고 기획력이 4점이구나"라고 정확히 파악해야 뒤의 분석이 의미가 있습니다.
- **가장 공을 들여야 하는 부분**: 이 노드의 정확도가 전체 시스템의 품질을 결정합니다.

**필요 데이터**:
- `(사용자 발화 : 추출된 JSON)` 쌍 데이터셋 (약 1,000건)
- 예시:
  ```json
  {
    "input": "코딩은 3점 정도 되고, 기획에 관심이 많아요",
    "output": {
      "competencies": [
        {"skill_name": "코딩", "skill_level": 3, "is_certified": false},
        {"skill_name": "기획", "skill_level": null, "is_certified": false}
      ],
      "interests": ["기획"]
    }
  }
  ```

**System Prompt 예시**:
```
당신은 사용자의 대화에서 역량 정보를 추출하는 전문가입니다.

사용자의 메시지에서 다음 정보를 추출하여 JSON 형식으로 반환하세요:
- skill_name: 스킬명 (예: "Python", "기획")
- skill_level: 숙련도 (1~5)
- is_certified: 자격/경험 여부 (true/false)

추출할 수 없는 정보는 null로 설정하세요.
확실하지 않은 정보는 추출하지 마세요. (Hallucination 방지)
```

**Tool 정의**:
```python
from langchain.tools import tool
from domain.user.model.user_competency import UserCompetency
from domain.user.base.database import AsyncSessionLocal

@tool
async def update_user_competency(
    user_id: int,
    skill_name: str,
    skill_level: int,
    is_certified: bool = False
) -> str:
    """사용자 역량 정보를 DB에 저장/업데이트"""
    async with AsyncSessionLocal() as session:
        # 기존 역량 조회
        existing = await session.query(UserCompetency).filter(
            UserCompetency.user_id == user_id,
            UserCompetency.skill_name == skill_name
        ).first()
        
        if existing:
            # 업데이트
            existing.skill_level = skill_level
            existing.is_certified = is_certified
        else:
            # 신규 생성
            new_competency = UserCompetency(
                user_id=user_id,
                skill_name=skill_name,
                skill_level=skill_level,
                is_certified=is_certified
            )
            session.add(new_competency)
        
        await session.commit()
        return f"{skill_name} 역량이 {skill_level}점으로 업데이트되었습니다."
```

### 6.4. 🔍 Trend_Analyst Node (The Researcher)

**베이스 모델**: **Llama-3.1-8B-Korean-Bllossom (Local)** 또는 **70B (Groq)**

**역할**:
- **SQL 생성**: "요즘 AI 분야 투자 속도가 어때?"라는 질문을 SQL로 변환하여 실시간 지표 조회
- **지표 해석**: 수치 데이터(Velocity Score)를 읽기 쉽게 설명
- **통계 기반 정보 제공**: `Velocity Score`가 높은 상위 트렌드 지표를 SQL로 조회하여 결과 반환

**튜닝 여부**: **O (QLoRA - Text-to-SQL)**
- 우리 프로젝트의 전용 테이블(`external_trend_data`) 구조를 완벽히 이해해야 합니다.
- 자연어 질문을 정확한 SQL 쿼리로 변환하는 능력이 핵심입니다.

**필요 데이터**:
- DB DDL(테이블 구조) - `external_trend_data` 스키마
- 지표 계산 로직 설명서
- 샘플 SQL 쿼리셋 (약 500건)
- 예시:
  ```json
  {
    "input": "요즘 AI 분야 투자 속도가 어때?",
    "output": "SELECT trend_name, velocity_score, funding_volume_growth FROM external_trend_data WHERE category LIKE '%AI%' ORDER BY velocity_score DESC LIMIT 5"
  }
  ```

**Tool 정의**:
```python
@tool
async def get_top_trends(limit: int = 5) -> str:
    """Velocity Score가 높은 상위 트렌드를 조회"""
    async with AsyncSessionLocal() as session:
        trends = await session.query(ExternalTrendData).order_by(
            ExternalTrendData.velocity_score.desc()
        ).limit(limit).all()
        
        result = []
        for trend in trends:
            result.append({
                "name": trend.trend_name,
                "velocity_score": trend.velocity_score,
                "opportunity_level": trend.opportunity_level,
                "category": trend.category
            })
        
        return json.dumps(result, ensure_ascii=False)
```

### 6.5. 💡 Insight_Coach Node (The Strategist)

**베이스 모델**: **Llama-3.1-70B (Groq)**

**역할**:
- **매칭 및 제언**: 사용자의 역량 점수와 미래 트렌드의 요구 스펙을 비교하여 '역량 갭'을 분석하고 로드맵 생성
- **개인화 전략 수립**: 사용자의 `persona_vector`와 트렌드 데이터를 비교하여 맞춤형 멘토링 텍스트 생성

**튜닝 여부**: **X (RAG 기반)**
- 튜닝보다는 실제 직무 로드맵 데이터나 교육 콘텐츠 데이터를 **RAG(검색 증강 생성)**로 넣어주는 것이 훨씬 정확합니다.
- Groq API를 사용하므로 로컬 VRAM 소모 없음

**필요 데이터**:
- 직무별 요구 역량 DB
- 추천 학습 콘텐츠 리스트 (온라인 강의, 도서 등)
- 사용자-트렌드 유사도 결과 (`persona_vector`와 `trend_vector`의 코사인 유사도)
- RAG 벡터 DB: 직무별 역량 요구사항, 학습 경로, 추천 콘텐츠

**System Prompt 예시**:
```
당신은 사용자의 진로를 상담하는 AI 코치입니다.

사용자의 현재 역량과 트렌드 데이터를 분석하여:
1. 역량 갭(Gap) 분석: 목표 트렌드에 필요한 역량과 현재 역량 비교
2. 추천 학습 경로: 부족한 역량을 보완할 수 있는 구체적인 학습 단계
3. 구체적인 행동 지침: 다음 주/다음 달에 할 수 있는 실천 가능한 액션 아이템

RAG로 제공된 직무별 역량 요구사항과 학습 콘텐츠를 참고하여 답변하세요.
```

### 6.6. 🎙️ Answer_Node (The Final Voice)

**베이스 모델**: **Llama-3.1-8B-Korean-Bllossom (Local)**

**역할**: 
- 모든 노드의 결과를 취합해 최종적으로 친절하고 명확한 대화문으로 정리
- 사용자에게 자연스러운 한국어로 응답 전달

**튜닝 여부**: **X (Prompting)**
- 최종 출력의 톤앤매너만 조절하면 됩니다.
- 로컬 8B 모델로 충분히 자연스러운 응답 생성 가능

**필요 데이터**:
- 앞선 노드들이 생성한 모든 중간 결과물
  - `extracted_data` (Profile_Manager에서 추출)
  - `trend_data` (Trend_Analyst에서 조회)
  - `insight` (Insight_Coach에서 생성)

**System Prompt 예시**:
```
당신은 사용자에게 친근하고 자연스러운 대화로 응답을 전달하는 전문가입니다.

각 노드에서 수집된 정보를 바탕으로 사용자에게 자연스러운 한국어로 응답하세요.
- 따뜻하고 격려하는 톤을 유지하세요
- 전문 용어는 쉽게 풀어서 설명하세요
- 구체적인 예시를 들어주세요
```

## 7. 자원 배분 및 구현 전략 (RTX 4070 Super 12GB 기준)

### 7.1. 하이브리드 모델 전략

**핵심 전략**: Groq(70B)의 지능을 핵심 순간에 빌려 쓰면서, 로컬 8B 모델로 VRAM을 아끼는 최적의 하이브리드 구조

| 전략 구분 | 내용 | 비고 |
|----------|------|------|
| **VRAM 관리** | 8B 로컬 모델은 **QLoRA(4-bit)**로 로드 (약 5~6GB 사용) | 나머지 VRAM은 임베딩 모델 및 Context Window용으로 할당 |
| **순차 실행** | 랭그래프의 특성을 이용해 **한 번에 하나의 로컬 노드만 활성화**하여 VRAM 충돌 방지 | Orchestrator(Groq)와 Insight_Coach(Groq)는 API이므로 로컬 자원 소모 없음 |
| **에이전트 시점** | **`Interview_Lead`**가 대화를 시작하도록 전역 상태(`State`)의 시작점을 설정 | 사용자가 접속하자마자 질문을 던지는 로직 |

### 7.2. 모델별 역할 분담

**Groq 70B 사용 노드** (API 호출, 로컬 VRAM 소모 없음):
- **Orchestrator**: 복잡한 판단과 검증이 필요한 경우
- **Insight_Coach**: 전략적 사고와 매칭 로직이 필요한 경우

**로컬 8B 사용 노드** (QLoRA 튜닝, VRAM 효율적 사용):
- **Interview_Lead**: 대화 리드 및 질문 생성
- **Profile_Manager**: 데이터 추출 (가장 중요 - QLoRA 필수)
- **Trend_Analyst**: SQL 생성 및 해석 (QLoRA 권장)
- **Answer_Node**: 최종 응답 생성

### 7.3. 튜닝 우선순위

1. **Profile_Manager (최우선)**: 
   - Hallucination 방지가 핵심
   - `(사용자 발화 : 추출된 JSON)` 데이터셋 1,000건 이상 필요
   - QLoRA 튜닝 필수

2. **Trend_Analyst (중요)**:
   - Text-to-SQL 정확도가 핵심
   - 샘플 SQL 쿼리셋 500건 이상 필요
   - QLoRA 튜닝 권장

3. **Interview_Lead (선택적)**:
   - Persona 특화 튜닝 가능
   - 강력한 System Prompt로도 대체 가능

## 8. 구현 시 주의할 점

### 8.1. 툴 콜링(Tool Calling)

- 각 노드들이 DB에 접근할 때는 LLM이 직접 쿼리를 짜게 하기보다, 미리 정의된 **파이썬 함수(Tools)**를 실행하도록 설계하세요.
- 보안 및 정확도 향상을 위해 SQL Injection 방지 및 데이터 검증이 필수입니다.

### 8.2. 루프(Loop) 제어

- 사용자가 불명확한 답변을 할 경우 오케스트레이터가 다시 질문을 던지도록 **순환 구조**를 설계할 수 있다는 점이 LangGraph의 최대 장점입니다.
- 최대 재시도 횟수를 설정하여 무한 루프를 방지하세요.

### 8.3. 에러 핸들링

- 각 노드에서 발생할 수 있는 에러를 처리하고, 사용자에게 친절한 에러 메시지를 제공하세요.
- DB 연결 실패, 모델 추론 실패 등에 대한 대비책을 마련하세요.

## 9. LangGraph 그래프 구성 예시

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 그래프 생성
workflow = StateGraph(AgentState)

# 노드 추가
workflow.add_node("interview_lead", interview_lead_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("profile_manager", profile_manager_node)
workflow.add_node("trend_analyst", trend_analyst_node)
workflow.add_node("insight_coach", insight_coach_node)
workflow.add_node("answer", answer_node)

# 엣지 추가
workflow.set_entry_point("interview_lead")  # 첫 접속 시 Interview_Lead부터 시작

# Interview_Lead에서 Orchestrator로
workflow.add_edge("interview_lead", "orchestrator")

# 조건부 엣지 (의도에 따라 분기)
workflow.add_conditional_edges(
    "orchestrator",
    route_intent,
    {
        "interview_lead": "interview_lead",  # 추가 정보 필요 시
        "profile_manager": "profile_manager",
        "trend_analyst": "trend_analyst",
        "insight_coach": "insight_coach",
        "answer": "answer"
    }
)

# Worker 노드에서 Answer 노드로
workflow.add_edge("profile_manager", "answer")
workflow.add_edge("trend_analyst", "answer")
workflow.add_edge("insight_coach", "answer")

# Interview_Lead에서도 Answer로 (질문만 하고 답변하는 경우)
workflow.add_edge("interview_lead", "answer")

# Answer 노드에서 종료
workflow.add_edge("answer", END)

# 체크포인트 메모리 설정 (대화 기록 유지)
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

## 10. 다음 단계

### 10.1. 우선 구현 항목

1. **Profile_Manager 노드 QLoRA 튜닝** ⭐⭐⭐ 최우선
   - **가장 공을 들여야 하는 부분**: 이 노드의 정확도가 전체 시스템의 품질을 결정
   - `(사용자 발화 : 추출된 JSON)` 데이터셋 구성 (1,000건 이상)
   - Hallucination 방지를 위한 정확한 데이터 추출 학습
   - QLoRA 튜닝으로 특화 모델 생성

2. **Interview_Lead 노드 구현** ⭐⭐ 중요
   - 프로필 완성도 체크 Tool 구현
   - 단계별 대화 가이드 로직 구현
   - "에이전트가 던질 역사적인 첫 번째 질문" 설계 및 프롬프트 엔지니어링
   - 로컬 8B 모델로 질문 생성 (Persona Tuning 선택적)

3. **오케스트레이터 의도 분류 로직**
   - "내 스킬 점수 좀 바꿔줘" vs "요즘 경제 트렌드 어때?" vs "추가 정보 필요" 구분
   - 프로필 완성도에 따른 라우팅 로직
   - Groq 70B 모델 연동 (Few-Shot Prompting)

4. **Trend_Analyst 노드 Text-to-SQL 튜닝**
   - 샘플 SQL 쿼리셋 구성 (500건 이상)
   - `external_trend_data` 테이블 구조 학습
   - QLoRA 튜닝으로 Text-to-SQL 특화

5. **상태 관리 시스템**
   - TypedDict 기반 State 정의
   - 대화 기록 관리
   - 컨텍스트 유지 메커니즘
   - Workflow Stage 관리 (아이스브레이킹 → 관심사 탐색 → 역량 파악 → 가치관 심화)

6. **RAG 시스템 구축** (Insight_Coach용)
   - 직무별 역량 요구사항 벡터 DB 구축
   - 학습 콘텐츠 메타데이터 벡터화
   - 유사도 검색 및 컨텍스트 주입

### 10.2. 향후 확장 계획

- **도서 추천 노드**: 트렌드에 맞는 학습 도서 추천
- **뉴스 요약 노드**: 관련 뉴스 기사 요약 및 분석
- **학습 진도 추적 노드**: 사용자의 학습 진도 모니터링 및 피드백

## 11. 참고 자료

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangGraph 튜토리얼](https://langchain-ai.github.io/langgraph/tutorials/)
- [Llama-3.1-8B-Korean-Bllossom 모델](https://huggingface.co/beomi/Llama-3.1-8B-Korean-Bllossom)
