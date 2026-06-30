// 개인화 선택 입력 옵션 — enum 한국어 라벨 + 관심 키워드 풀(12섹터+직무군)

export interface Option { value: string; label: string; }

export const GENDER_OPTIONS: Option[] = [
  { value: "male", label: "남성" },
  { value: "female", label: "여성" },
  { value: "other", label: "기타" },
];

export const CURRENT_STATUS_OPTIONS: Option[] = [
  { value: "student", label: "학생" },
  { value: "job_seeking", label: "구직 중" },
  { value: "employed", label: "재직 중" },
  { value: "career_switch", label: "전환 준비" },
];

export const EDUCATION_OPTIONS: Option[] = [
  { value: "high_school", label: "고졸" },
  { value: "undergrad", label: "대학 재학" },
  { value: "bachelor", label: "학사" },
  { value: "master", label: "석사" },
  { value: "phd", label: "박사" },
];

export const WORK_STYLE_OPTIONS: Option[] = [
  { value: "stability", label: "안정 지향" },
  { value: "challenge", label: "도전 지향" },
  { value: "balanced", label: "균형" },
];

export const COMPANY_SIZE_OPTIONS: Option[] = [
  { value: "startup", label: "스타트업" },
  { value: "sme", label: "중소기업" },
  { value: "large", label: "대기업" },
  { value: "public", label: "공공기관" },
];

export const WORK_TYPE_OPTIONS: Option[] = [
  { value: "office", label: "사무실" },
  { value: "remote", label: "원격" },
  { value: "hybrid", label: "하이브리드" },
];

export const WORK_VALUE_OPTIONS: Option[] = [
  { value: "growth", label: "성장" },
  { value: "work_life_balance", label: "워라밸" },
  { value: "autonomy", label: "자율성" },
  { value: "impact", label: "사회적 임팩트" },
  { value: "compensation", label: "보상" },
];

// 관심 분야 — 라벨이 곧 저장값(interest_keywords). 백엔드 Pulse 12섹터와 정렬.
export const INTEREST_SECTORS: Option[] = [
  { value: "AI·데이터", label: "AI·데이터" },
  { value: "반도체", label: "반도체" },
  { value: "바이오·헬스", label: "바이오·헬스" },
  { value: "에너지·기후", label: "에너지·기후" },
  { value: "식품·농업", label: "식품·농업" },
  { value: "핀테크", label: "핀테크" },
  { value: "모빌리티", label: "모빌리티" },
  { value: "콘텐츠·크리에이터", label: "콘텐츠·크리에이터" },
  { value: "에듀테크", label: "에듀테크" },
  { value: "뷰티·패션", label: "뷰티·패션" },
  { value: "물류", label: "물류" },
  { value: "사회서비스", label: "사회서비스" },
];

export const JOB_FAMILIES: Option[] = [
  { value: "엔지니어링", label: "엔지니어링" },
  { value: "데이터·AI", label: "데이터·AI" },
  { value: "기획·PM", label: "기획·PM" },
  { value: "디자인", label: "디자인" },
  { value: "마케팅·영업", label: "마케팅·영업" },
  { value: "연구개발", label: "연구개발" },
  { value: "운영·CS", label: "운영·CS" },
];
