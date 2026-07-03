# RIASEC(홀랜드) 채점 방식 조사 — 자유대화 기반 6축 점수화 설계 근거

> 목적 — AI 상담실이 자유대화에서 RIASEC 6축(R·I·A·S·E·C) 점수를 산출하는 설계(`user_self_model.riasec = {"scores": {...0-100}, "top_codes": [...]}`, `backend/domain/user_intelligence/models/bases/user_self_model.py`, 스펙 `backend/docs/superpowers/specs/2026-07-01-ai-coach-self-model-design.md`)의 근거로, 실제 정식 검사가 어떻게 채점되는지와 홀랜드 원전 이론의 채점 원리를 조사.
> 조사일 — 2026-07-03. 방법 — 공식 사이트/발간기관 PDF 우선(WebFetch+pdftotext 직접 추출), 학술 소스(O*NET 공식 기술 매뉴얼, arXiv 논문) 병행. 일부 공식 매뉴얼은 접근 제한(403/PDF 암호화)으로 부분 정보만 확보 — 해당 항목은 '불확실'로 명시.

---

## 1. 검사별 채점 절차 요약

| 검사 | 발행처 | 문항 구성 | 응답 척도 | 원점수 | 표준화/변환 | 코드 결정 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| **워크넷 직업선호도검사 S형**(흥미검사 파트) | 한국고용정보원(KEIS), 2011년 개정 | 총 204문항 = 6요인 x 34문항(활동/유능성/직업/선호분야/일반성향 5개 하위척도에 분산) | 불확실(원문 브로슈어에 리커트 점수 미기재) | 요인별 34문항 단순 합산 | 요인별 백분율(전체 문항의 원점수를 100점 환산) 사용 확인. T점수 변환 절차는 조사 자료에서 확인 못함(불확실) | "6개 흥미요인점수 중 가장 큰 2개점수를 이용하여 개인별 흥미코드(예: SA유형)를 결정" — 2자리, 최댓값 순 | 요인별 Cronbach alpha .901~.933(현실 .931/탐구 .908/예술 .925/사회 .914/진취 .933/관습 .901) |
| **워크넷 직업선호도검사 L형** | KEIS, 2011년 개정 | 흥미검사(S형과 동일 구조, 6요인x34=204) + 성격검사(Big5 유사 5요인) + 생활사검사(8요인) 3부 구성 | 상동(불확실) | 상동 | 상동 | 상동(2자리 코드) | 흥미검사 alpha .90~.93(동일) |
| **커리어넷 직업흥미검사 H형**(고등학생용) | 한국직업능력연구원(KRIVET) | 중학생 127문항/고등학생 126문항, 20분 | 불확실 | 불확실 | 불확실 | 불확실 | 불확실 |
| **커리어넷 직업흥미검사 K형**(중고등학생용) | KRIVET | 중학생 136문항/고등학생 153문항, 15~20분 | 불확실 | 불확실 | 불확실 | 불확실 | 불확실 |
| **Holland 적성검사**(민간, 안현의·안창규, 한국가이던스) | 이화여대·부산대 공동개발 | 성격적성·능력적성·직업적성 등 다중 영역에서 RIASEC 각각 채점 | 불확실 | 원점수 -> 백분율(원점수/전체문항수x100) | 규준집단 대비 백분위(1순위 코드를 가진 100명 중 위치) 병행 제공. "일치도" 지표: 성격/능력/직업적성 각 0~6점, 종합 0~18점 | 종합점수 최댓값 2개로 1차(주코드)·2차(부코드) 결정. 명시: "여기서는 단순 통계치에 따라 결정" | 문서 내 명시 없음(불확실) |
| **O*NET Interest Profiler Long Form**(미국, 공식 원조 참고용) | US Dept. of Labor / National O*NET Center | 180문항 = 6요인x30문항 | 3점(Like/Unsure/Dislike) | Like 응답만 요인별 단순 합산, 범위 0~30 | 없음 — 원점수(raw sum)를 그대로 순위 비교에 사용, T점수·백분위 변환 없음 | 원점수 최댓값 상위 2~3개를 순위대로 나열해 Holland 코드 결정(자가채점 시 97%+ 정확도) | alpha .93~.97(요인별) |
| **O*NET Interest Profiler Short Form**(웹) | 상동 | 60문항 = 6요인x10문항 | 지면판: 이분(체크) / 웹판: 5점(0=strongly dislike ~ 4=strongly like, 이모지 앵커) | 요인별 합산, 범위 0~40 | 없음(원점수 직접 비교) | 상동(최댓값 순) | alpha .78~.90(표본별 편차) |
| **O*NET Interest Profiler Mini-IP**(모바일) | 상동 | 30문항 = 6요인x5문항 | 5점(상동) | 요인별 합산, 범위 0~20 | 없음 | 상동 | alpha .70~.81 |

**출처**
- 워크넷 S형/L형 구성·문항수·신뢰도·코드결정 — 한국고용정보원 [직업심리검사 가이드] PDF(직접 텍스트 추출·인용, keis.or.kr 배포). 원문 인용: "6개 흥미요인점수 중 가장 큰 2개점수를 이용하여 개인별 흥미코드(예 : 사회형/예술형(SA유형))를 결정합니다."
- Holland 적성검사 해석지침서(안현의·안창규, 이화여대/부산대) PDF — 일치도·백분위·코드결정 절차 원문 인용.
- 커리어넷 H형/K형 문항수 — krivet.re.kr(활용안내서 목차), career.go.kr(검사 소개 페이지). 채점 세부는 접근 실패(403/바이너리).
- O*NET Interest Profiler 전 항목 — O*NET Interest Profiler Manual(공식 기술 매뉴얼, Chapter 3 Scoring/Chapter 4 Item Development/Chapter 5 Reliability), onetcenter.org/dl_files/IP_Manual.pdf — 이 문서에서 가장 상세하고 명확한 1차 자료 확보(pdftotext로 전문 추출·직접 인용).

### 워크넷 S형 요인 간 상관행렬(육각모형 실증 근거)
KEIS 가이드에서 추출한 흥미검사 6요인 간 피어슨 상관(원문 표):

| | 현실 | 탐구 | 예술 | 사회 | 진취 | 관습 |
|---|---|---|---|---|---|---|
| 현실 | 1.00 | .306 | .015 | .006 | .141 | -.013 |
| 탐구 | | 1.00 | .349 | .283 | .255 | .185 |
| 예술 | | | 1.00 | .466 | .290 | .141 |
| 사회 | | | | 1.00 | .449 | .408 |
| 진취 | | | | | 1.00 | .378 |
| 관습 | | | | | | 1.00 |

인접(예: 현실-탐구 .306, 사회-진취 .449)은 상대적으로 높고, 대각/원거리(현실-사회 .006, 현실-예술 .015)는 0에 가깝거나 음수 — 육각모형(인접>대안>대극) 가설을 이 한국 표준화 데이터가 실증적으로 뒷받침.

O*NET 문항개발 챕터도 동일 원리를 문항선정 알고리즘에 명시: "a Realistic item should correlate most highly with its target scale, next strongest with its adjacent scales, less strongly with its alternative scales, and least strongly with its opposite scale."(O*NET IP Manual, Ch.4)

---

## 2. 6축 독립 합산 점수라는 근거

**결론 — 정당화됨.** 모든 조사된 검사(워크넷 S/L형, Holland 적성검사, O*NET IP 전 버전)가 6개 축을 각각 별도 문항 풀로 독립 채점하고, 각 축의 원점수를 단순 합산(Like 카운트 포함)으로 산출한다. 6축은 상호 배타적 문항 세트이며 등급화된 리커트 응답의 합계이지 강제선택(ipsative)이 아니다. 다만:

- 코드 결정 단계에서는 상대 순위(최댓값 top-2/3)를 쓴다 — 절대 점수 자체는 축별 독립이지만, "무엇이 나를 대표하는가"는 순위 비교로 뽑는다. 즉 저장은 축별 절대값(레이더 O), 해석/코드는 상대 순위라는 이원 구조가 검사 전반의 공통 패턴.
- 6축은 완전 독립이 아니라 육각모형에 따른 상관 구조(인접 축 정적 상관 .3~.45, 대극 축 0에 가까움)를 갖는다 — 통계적 독립이 아니라 "이론적으로 예측되는 상관 패턴을 갖는 준독립 축". 레이더 시각화에는 문제없으나, 한 축이 오르면 인접 축도 약간 오르는 경향은 자연스러운 것으로 이상 신호가 아님.
- O*NET IP는 표준점수 변환을 아예 쓰지 않는다 — 원점수 그대로 저장·비교. 반면 한국 Holland 적성검사는 규준집단 대비 백분위까지 추가 제공(상대적 유용성 판단용). 두 접근 모두 축별 원점수 독립 저장은 공통이고, 표준화 여부만 제품 차이.

**반례/주의점**
- 문항 수가 다른데(예: Long Form 30문항/축 vs Mini-IP 5문항/축) 원점수 범위가 다르므로(0~30 vs 0~5), 원점수 자체를 축 간 직접 비교하려면 반드시 0~100 등 공통 스케일로 정규화해야 함 — 현재 riasec.scores가 0~100 고정 스케일인 설계는 이 문제를 이미 회피하고 있어 타당.
- Holland 적성검사의 "일치도" 지표는 RIASEC 축 간 비교가 아니라 검사 영역(성격/능력/직업) 간 비교다 — 우리 설계의 "축별 confidence"와는 다른 개념이므로 그대로 차용하지 말 것.

---

## 3. 홀랜드 이론 핵심 개념 (원전)

- **일관성(Consistency)** — 개인의 상위 2개 코드가 육각모형에서 얼마나 인접한가. 인접(RI)=High, 대안(RA)=Average, 대극(RS)=Low. 일관성이 높을수록 흥미 프로파일이 이론적으로 안정적.
- **변별도(Differentiation)** — 6축 점수의 편차(peakedness). 한두 축만 높고 나머지는 낮으면 변별도 高, 6축이 고르게 비슷하면 변별도 低(흥미가 아직 분화되지 않았다는 뜻으로 해석). 최신 방법론은 코사인 적합 함수(cosine fit)로 조작적 정의하는 것이 전통적 지표보다 우수함이 보고됨.
- **일치도(Congruence)** — 개인 흥미코드와 환경(직업)코드의 부합 정도. 만족도·지속성·수행과 상관.
- **계산(Calculus)** — 육각모형상 모든 유형 쌍의 거리 기반 관계 총합.
- 한국 Holland 적성검사는 "변별도"를 1순위 코드 긍정응답률, "일치도"를 검사 전후/영역 간 코드 비교로 조작화해 결과지에 노출.

**출처** — Holland의 hexagon/consistency/differentiation 개념: ScienceDirect, "An enhanced examination of Holland's consistency and differentiation hypotheses"(sciencedirect.com/science/article/abs/pii/S0001879114000219), iResearchNet Holland's Theory 요약(psychology.iresearchnet.com/counseling-psychology/counseling-theories/hollands-theory/); Holland 적성검사 해석지침서(안현의·안창규) 원문.


---

## 4. 자유대화 기반 점수화 설계 원칙 (제안 5개)

1. **축별 독립 0~100 절대 점수 + 근거 개수 기반 raw accumulation** — 정식 검사가 "축마다 별도 문항 풀 -> 단순 합산"하듯, 대화에서도 축마다 독립적으로 근거를 누적하고 축 간 비교(순위)는 저장이 아닌 표시 단계에서만 계산한다(현 스펙의 scores+top_codes 이원 구조와 일치. 2026-07-01-ai-coach-self-model-design.md 4.1절 참고).
2. **표본이 적을 때 중립(50)으로 shrink, 과신 금지** — O*NET IP의 IRT 분석은 문항 수(=관측치 수)가 적을수록(Mini-IP 5문항/축 alpha .70~.81) 신뢰도가 떨어지고, 짧은 형은 표준오차가 커짐을 실증. arXiv:2602.15848(2026, Univ. of Tartu) 논문이 사용한 실제 LLM 프롬프트도 동일 원칙을 명시: "If information is insufficient for a particular trait, indicate low confidence and score conservatively toward the middle range (50-70)". -> 근거 evidence 개수가 임계치 미만인 축은 50(중립) 방향으로 shrink하고 confidence를 낮게 표시.
3. **자기서술(explicit self-report)보다 행동/서사 근거(implicit indicator)에 더 큰 가중치** — 동일 arXiv 논문의 프롬프트 원칙: "weight behavioral evidence more heavily than self-descriptions... look for implicit indicators (what they show) vs explicit claims (what they say)". 코치 대화에서 "저는 사회형이에요" 같은 명시적 자기규정보다 "사람들 앞 발표에서 에너지를 얻는다" 같은 구체 일화에 더 높은 confidence를 부여.
4. **인접 축 상관은 정상, 완전 무관은 의심 신호** — 워크넷 실측 상관행렬(1절)에 따르면 인접 축(예: 사회-진취 .45)은 자연스럽게 동반 상승한다. 대화 추출기가 인접 축들을 극단적으로 반대 방향(한쪽 100, 인접 0)으로 추정하면 근거 재검토 신호로 삼을 수 있다(단, 강제는 아님 — 실제로 그런 사람도 존재).
5. **코드(top_codes)는 절대점수 순위에서만 파생, 별도 로직 금지** — 모든 조사 검사가 "요인점수 중 가장 큰 2(~3)개"로 코드를 정하듯, top_codes는 scores 확정 후 항상 그 순위에서 기계적으로 파생시키고 코드 자체에 독립 가중치/로직을 넣지 않는다(1차 코드=주코드가 진로 방향의 핵심이라는 실무 해석과도 일치, Holland 적성검사 지침서 인용: "1, 2차 진로코드는 RIASEC별로 종합점수가 가장 높은 순으로 두 자리 코드를 결정").

**참고 — 완전히 확인하지 못한 부분(불확실)**
- 정식 검사가 명시적 "신뢰구간"이나 "최소 문항수 미달 시 결과 보류" 장치를 두는지는 조사 자료에서 직접 확인되지 않음. 대신 간접 증거로 O*NET이 문항수별로 별도 폼(Long/Short/Mini)을 두고 각 폼의 신뢰도(alpha)를 다르게 명시해 "짧은 검사는 신뢰도가 낮다"는 점을 공식적으로 인정하는 방식을 취함 — 우리 설계에서는 이를 "근거 개수 구간별 confidence 등급"으로 변환해 참고할 수 있음.
- 커리어넷 H형/K형의 정확한 채점식은 접근 실패로 미확인. 구조적으로 워크넷과 동일한 Holland 이론 기반임은 KRIVET/커리어넷 공식 페이지로 확인되나, 세부 공식은 후속 조사 필요 시 KRIVET 고객센터(044-415-5003) 문의 권장.
- LLM 대화 기반 Big Five/RIASEC 추정의 신뢰 구간·최소 대화량에 대한 정량 기준은 학계에 아직 확립된 표준이 없음(arXiv:2602.15848도 N=33 소규모 파일럿, r=0.38~0.58 수준). "안전한 최소 근거 수" 임계치는 우리 프로젝트가 자체 결정해야 하는 영역.

---

## 5. 출처 목록

- 한국고용정보원, [직업심리검사 가이드](직업선호도검사 S형/L형 포함) — keis.or.kr/keis/ko/cmmn/download.do (검색 경유 확보; 실제 원문은 워크넷 가이드 PDF에서 S/L형 세부 인용)
- 워크넷(고용노동부) 직업심리검사 — work.go.kr/consltJobCarpa/jobPsyExamNew/jobPsyExamList.do
- 커리어넷 직업흥미검사 H형/K형 소개 — career.go.kr/cnet/front/examen/inspctIntroPopupF.do?QESTNR_SEQ=18 , krivet.re.kr/kor/sub.do?menuSn=12&pstNo=PB0000000186
- Holland 적성검사 해석지침서(안현의·안창규, 이화여대/부산대) — ssproxy.ucloudbiz.olleh.com 경유 PDF(Inpsyt/HOLLAND 자료실)
- O*NET Interest Profiler Manual(공식, National Center for O*NET Development) — onetcenter.org/dl_files/IP_Manual.pdf (Ch.3 Scoring, Ch.4 Item Development, Ch.5 Reliability Evidence)
- Holland의 consistency/differentiation — ScienceDirect, "An enhanced examination of Holland's consistency and differentiation hypotheses" — sciencedirect.com/science/article/abs/pii/S0001879114000219
- Holland's Theory 개관 — iResearchNet — psychology.iresearchnet.com/counseling-psychology/counseling-theories/hollands-theory/
- Matsenas et al., "Can LLMs Assess Personality? Validating Conversational AI for Trait Profiling"(Univ. of Tartu, arXiv:2602.15848, 2026-01-23) — arxiv.org/pdf/2602.15848
- (2차 참고, 미검증) InterviewBERT류 대화 기반 성격 추정 상관계수 약 0.37 — WebSearch 요약 인용, 원문 미확인이므로 인용 시 별도 검증 필요

---

## 부록 — 이번 조사에서 접근 실패한 자료(추가 조사 시 참고)
- 커리어넷 직업흥미검사 H형 활용안내서 전문(KRIVET, "채점 방법" 25p 존재 확인했으나 원문 텍스트 미추출)
- 대학생 및 성인을 위한 직업선호도검사(L형) 상담자 매뉴얼(jinlo.net) — 인증서 만료/403으로 접근 불가
- 워크넷 흥미검사 실제 문항 예시 및 응답 리커트 점수(몇 점 척도인지) — 브로슈어 수준 자료에서는 확인 불가, 실제 검사지 또는 기술 매뉴얼 필요
