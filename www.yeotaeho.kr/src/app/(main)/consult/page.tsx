"use client";

import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Brain,
  ChevronRight,
  MessageCircle,
  Radar as RadarIcon,
  SendHorizonal,
  Sparkles,
  Terminal,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

type ChatRole = "ai" | "user" | "system";

type ChatMessage =
  | { id: string; role: "ai"; content: string; rich?: "card"; cardTitle?: string }
  | { id: string; role: "user"; content: string }
  | { id: string; role: "system"; content: string };

const INDIGO = "#4F46E5";

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "m0",
    role: "ai",
    content:
      "안녕하세요. Deep Discovery 세션입니다. 먼저 가치관을 살펴볼게요. 어떤 환경에서 일할 때 가장 에너지가 난다고 느끼나요?",
  },
];

const PHASE1_CHIPS = [
  "안정적인 대기업",
  "성장하는 스타트업",
  "연구·학계",
  "아직 잘 모르겠어요",
];

export default function ConsultPage() {
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const formId = useId();

  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [phase, setPhase] = useState<1 | 2 | 3>(1);
  const [dialogStep, setDialogStep] = useState(0);
  const [input, setInput] = useState("");
  const [quickReplies, setQuickReplies] = useState<string[] | null>(PHASE1_CHIPS);
  const [keywords, setKeywords] = useState<string[]>([
    "문제해결",
    "데이터 기반",
  ]);
  const [chartReady, setChartReady] = useState(false);

  const progressPercent = useMemo(() => {
    if (phase === 1) return 28 + dialogStep * 12;
    if (phase === 2) return 62 + Math.min(dialogStep * 8, 24);
    return 96;
  }, [phase, dialogStep]);

  const radarRows = useMemo(() => {
    const base = { 구조화: 58, 실행력: 62, 탐구: 55, 협업: 60, 도메인싱크: 52 };
    const bump = dialogStep * 3 + (phase - 1) * 8;
    return [
      { subject: "구조화", value: Math.min(98, base.구조화 + bump), fullMark: 100 },
      { subject: "실행력", value: Math.min(98, base.실행력 + bump - 2), fullMark: 100 },
      { subject: "탐구", value: Math.min(98, base.탐구 + bump + 4), fullMark: 100 },
      { subject: "협업", value: Math.min(98, base.협업 + bump - 1), fullMark: 100 },
      { subject: "도메인싱크", value: Math.min(98, base.도메인싱크 + bump + 6), fullMark: 100 },
    ];
  }, [phase, dialogStep]);

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, quickReplies, scrollToBottom]);

  useEffect(() => {
    setChartReady(true);
  }, []);

  const pushKeywords = useCallback((tags: string[]) => {
    setKeywords((prev) => {
      const next = [...prev];
      for (const t of tags) {
        if (!next.includes(t)) next.unshift(t);
      }
      return next.slice(0, 12);
    });
  }, []);

  const runAfterUserMessage = useCallback(
    (text: string) => {
      setMessages((prev) => [...prev, { id: uid(), role: "user", content: text }]);
      setQuickReplies(null);
      setInput("");

      window.setTimeout(() => {
        if (phase === 1 && dialogStep === 0) {
          setDialogStep(1);
          pushKeywords(["가치클러스터", text.slice(0, 10)]);
          setMessages((p) => [
            ...p,
            {
              id: uid(),
              role: "ai",
              content:
                "좋습니다. 그 선택과 연결된 최근 경험을 한 문장으로 남겨 주세요. 짧게라도 괜찮습니다.",
            },
          ]);
          return;
        }
        if (phase === 1 && dialogStep === 1) {
          setPhase(2);
          setDialogStep(0);
          pushKeywords(["성향_요약", "#열정"]);
          setMessages((p) => [
            ...p,
            {
              id: uid(),
              role: "system",
              content:
                "가치관 분석이 완료되었습니다. 다음은 실무 역량 검증을 시작하겠습니다.",
            },
            {
              id: uid(),
              role: "ai",
              rich: "card",
              cardTitle: "역량 시나리오",
              content:
                "API 장애가 발생했습니다. 우선 어떤 신호를 먼저 확인하고, 롤백 vs 핫픽스 중 무엇을 기준으로 결정하시겠어요? 근거를 짧게 서술해 주세요.",
            },
          ]);
          return;
        }
        if (phase === 2 && dialogStep === 0) {
          setDialogStep(1);
          pushKeywords(["FastAPI_중급", "장애대응", "#성장중심"]);
          setMessages((p) => [
            ...p,
            {
              id: uid(),
              role: "ai",
              content:
                "응답을 바탕으로 구조화·우선순위 역량이 확인되었습니다. 잠재력 리포트 초안을 우측 패널에 반영했습니다.",
            },
          ]);
          setPhase(3);
          return;
        }
        if (phase === 3) {
          setMessages((p) => [
            ...p,
            {
              id: uid(),
              role: "ai",
              content:
                "추가로 다듬고 싶은 목표가 있으면 이어서 말씀해 주세요. 또는 하단 액션으로 로드맵·코치로 연결할 수 있습니다.",
            },
          ]);
        }
      }, 380);
    },
    [dialogStep, phase, pushKeywords]
  );

  const sendInput = () => {
    const t = input.trim();
    if (!t) return;
    if (phase === 1 && dialogStep === 0) {
      return;
    }
    runAfterUserMessage(t);
  };

  const onChip = (label: string) => {
    if (phase !== 1 || dialogStep !== 0) return;
    runAfterUserMessage(label);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendInput();
    }
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200/80 pb-4 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-indigo-100 p-3 text-indigo-700 ring-1 ring-indigo-200/60 dark:bg-indigo-900/30 dark:text-indigo-300 dark:ring-indigo-900/40">
            <MessageCircle className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              AI 상담실 <span className="text-indigo-600">Deep Discovery</span>
            </h1>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              실시간 맥락 분석 · 단계별 역량 추출 · 우측 라이브 리포트 동기화
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs font-mono text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
          <Terminal className="h-3.5 w-3.5 text-indigo-600" />
          <span>session</span>
          <span className="text-slate-400">·</span>
          <span className="font-semibold text-indigo-700">
            phase_{phase}
          </span>
          <span className="text-slate-400">·</span>
          <span>graph_node=live</span>
        </div>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,13fr)_minmax(300px,7fr)] lg:items-stretch">
        {/* Left: chat canvas */}
        <section
          className="flex min-h-[min(72vh,720px)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-b from-white to-slate-50 shadow-[0_1px_0_rgba(15,23,42,0.04)] dark:border-slate-700 dark:from-slate-800 dark:to-slate-900 dark:shadow-none"
        >
          <div className="flex items-center justify-between border-b border-slate-200/90 bg-white/90 px-4 py-3 backdrop-blur dark:border-slate-700 dark:bg-slate-900/90">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <Activity className="h-3.5 w-3.5 text-emerald-600" />
              Interactive · 메시지 피드
            </div>
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-mono text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              turn_index≈{messages.filter((m) => m.role !== "system").length}
            </span>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto bg-white px-4 py-4 dark:bg-slate-800">
            <AnimatePresence initial={false}>
              {messages.map((m) => {
                if (m.role === "system") {
                  return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex justify-center py-2"
                    >
                      <div className="max-w-[90%] rounded-full border border-indigo-100 bg-indigo-50/90 px-4 py-2 text-center text-xs font-medium text-indigo-800 ring-1 ring-indigo-100/80 dark:border-indigo-900/40 dark:bg-indigo-900/30 dark:text-indigo-200 dark:ring-indigo-900/30">
                        {m.content}
                      </div>
                    </motion.div>
                  );
                }
                if (m.role === "user") {
                  return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex justify-end"
                    >
                      <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-indigo-600 px-4 py-3 text-sm leading-relaxed text-white shadow-sm">
                        {m.content}
                      </div>
                    </motion.div>
                  );
                }
                return (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-start"
                  >
                    <div className="max-w-[88%] space-y-2">
                      {m.rich === "card" && m.cardTitle ? (
                        <div className="overflow-hidden rounded-2xl rounded-tl-md border border-slate-200 bg-slate-100/90 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                          <div className="flex items-center gap-2 border-b border-slate-200/80 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                            <Brain className="h-3.5 w-3.5 text-indigo-600" />
                            {m.cardTitle}
                          </div>
                          <p className="px-3 py-3 text-sm leading-relaxed text-slate-800 dark:text-slate-200">
                            {m.content}
                          </p>
                        </div>
                      ) : (
                        <div className="rounded-2xl rounded-tl-md bg-slate-100 px-4 py-3 text-sm leading-relaxed text-slate-900 dark:bg-slate-900 dark:text-slate-100">
                          {m.content}
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
            <div ref={chatEndRef} />
          </div>

          {/* Quick replies + input */}
          <div className="border-t border-slate-200 bg-white/95 px-3 pb-3 pt-2 backdrop-blur dark:border-slate-700 dark:bg-slate-900/95">
            <AnimatePresence mode="popLayout">
              {quickReplies && quickReplies.length > 0 && (
                <motion.div
                  key="chips"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-2 flex flex-wrap gap-2"
                >
                  {quickReplies.map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => onChip(chip)}
                      className="rounded-full border border-indigo-200 bg-white px-3 py-1.5 text-left text-xs font-semibold text-indigo-800 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 dark:border-indigo-900/40 dark:bg-slate-800 dark:text-indigo-300 dark:hover:bg-indigo-900/30"
                    >
                      {chip}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            <form
              id={formId}
              className="flex items-end gap-2 rounded-xl border border-slate-200 bg-[#F8FAFC] p-2 ring-1 ring-slate-900/5 focus-within:border-indigo-300 focus-within:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900"
              onSubmit={(e) => {
                e.preventDefault();
                sendInput();
              }}
            >
              <label htmlFor={`${formId}-input`} className="sr-only">
                답변 입력
              </label>
              <input
                ref={inputRef}
                id={`${formId}-input`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  phase === 1 && dialogStep === 0
                    ? "위 선택지를 먼저 눌러 주세요 (또는 칩 사용)"
                    : "답변을 입력하고 Enter로 전송…"
                }
                disabled={phase === 1 && dialogStep === 0}
                className="min-h-[44px] flex-1 rounded-lg border-0 bg-transparent px-2 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-60 dark:text-slate-100 dark:placeholder:text-slate-500"
              />
              <button
                type="submit"
                disabled={phase === 1 && dialogStep === 0 && !input.trim()}
                className="inline-flex h-10 shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-3 text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-40"
                aria-label="전송"
              >
                <SendHorizonal className="h-4 w-4" />
              </button>
            </form>
            <p className="mt-1.5 px-1 text-[11px] text-slate-500 dark:text-slate-500">
              가치관 단계는 <strong className="font-semibold text-slate-700 dark:text-slate-300">Quick Reply</strong>
              로 빠르게, 역량 단계는 <strong className="font-semibold text-slate-700 dark:text-slate-300">서술형 입력</strong>
              으로 받습니다.
            </p>
          </div>
        </section>

        {/* Right: live panel */}
        <aside className="flex flex-col gap-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-500">
                Live result
              </p>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 ring-1 ring-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-300 dark:ring-emerald-900/40">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                sync
              </span>
            </div>
            <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
              나의 발견 {phase} / 3 ·{" "}
              <span className="text-indigo-600">{Math.round(progressPercent)}%</span>
            </p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200/80 dark:bg-slate-700 dark:ring-slate-700">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-emerald-500"
                initial={false}
                animate={{ width: `${progressPercent}%` }}
                transition={{ type: "spring", stiffness: 120, damping: 22 }}
              />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-[10px] font-medium text-slate-600 dark:text-slate-400">
              <span className={phase >= 1 ? "text-indigo-700" : ""}>① 가치관</span>
              <span className={phase >= 2 ? "text-indigo-700" : ""}>② 역량</span>
              <span className={phase >= 3 ? "text-indigo-700" : ""}>③ 리포트</span>
            </div>
          </div>

          <div className="flex flex-1 flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
              <RadarIcon className="h-4 w-4 text-indigo-600" />
              역량 · 성향 레이더
            </div>
            <div className="h-[240px] w-full min-w-0">
              {chartReady ? (
                <ResponsiveContainer width="100%" height={240}>
                  <RadarChart cx="50%" cy="50%" outerRadius="72%" data={radarRows}>
                    <PolarGrid stroke="#e2e8f0" />
                    <PolarAngleAxis
                      dataKey="subject"
                      tick={{ fill: "#64748b", fontSize: 11 }}
                    />
                    <PolarRadiusAxis
                      angle={30}
                      domain={[0, 100]}
                      tick={false}
                      axisLine={false}
                    />
                    <Radar
                      name="프로필"
                      dataKey="value"
                      stroke={INDIGO}
                      fill={INDIGO}
                      fillOpacity={0.22}
                      isAnimationActive
                      animationDuration={600}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-xl bg-slate-50 text-xs text-slate-400 dark:bg-slate-900 dark:text-slate-500">
                  차트 로딩…
                </div>
              )}
            </div>
            <p className="mt-1 text-center text-[11px] text-slate-500 dark:text-slate-500">
              턴이 진행될 때마다 영역이 소폭 갱신됩니다 (목업).
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-300">
              <Sparkles className="h-4 w-4 text-amber-500" />
              라이브 키워드
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <AnimatePresence mode="popLayout">
                {keywords.map((k, i) => (
                  <motion.span
                    key={k}
                    layout
                    initial={{ opacity: 0, scale: 0.92 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className="rounded-full border border-indigo-100 bg-gradient-to-r from-indigo-50 to-white px-2.5 py-1 text-[11px] font-semibold text-indigo-800 shadow-sm ring-1 ring-indigo-100/60 dark:border-indigo-900/40 dark:from-indigo-900/30 dark:to-slate-800 dark:text-indigo-300 dark:ring-indigo-900/30"
                  >
                    #{k}
                  </motion.span>
                ))}
              </AnimatePresence>
            </div>
          </div>

          <div className="rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4 dark:border-indigo-900/40 dark:bg-indigo-900/20">
            <p className="text-xs font-semibold text-indigo-900 dark:text-indigo-200">성향 한 줄 (목업)</p>
            <p className="mt-2 text-sm font-medium leading-snug text-slate-900 dark:text-slate-100">
              에너지 전환·데이터 교차점에서 구조화 실행력이 두드러지는 빌더형
            </p>
            <div className="mt-4 flex flex-col gap-2">
              <Link
                href="/roadmap"
                className="inline-flex items-center justify-center gap-1 rounded-xl bg-indigo-600 px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700"
              >
                분석 결과로 로드맵 만들기
                <ChevronRight className="h-4 w-4" />
              </Link>
              <div className="flex flex-wrap gap-2">
                <Link
                  href="/"
                  className="inline-flex flex-1 items-center justify-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Chance 보기
                </Link>
                <Link
                  href="/coach"
                  className="inline-flex flex-1 items-center justify-center rounded-xl border border-indigo-200 bg-white px-3 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-50 dark:border-indigo-900/40 dark:bg-slate-900 dark:text-indigo-300 dark:hover:bg-indigo-900/30"
                >
                  AI 코치
                </Link>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
