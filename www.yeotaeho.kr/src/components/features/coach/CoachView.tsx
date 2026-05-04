"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Paperclip,
  SendHorizonal,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  COACH_ACTIVE_FOCUS,
  DEMO_ATTACHED_CONTEXTS,
  type CoachAttachedContext,
  type CoachWalletItem,
} from "@/data/coachContext";
import { InsightWalletPanel } from "./InsightWalletPanel";

type CoachMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  code?: string;
  badge?: string;
};

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const PYTHON_SNIPPET = `from dataclasses import dataclass
from enum import Enum

class Factor(str, Enum):
    SCOPE1 = "scope1"
    SCOPE2 = "scope2"

@dataclass(frozen=True)
class ScoreInput:
    factor: Factor
    raw_value: float

class RuleCalculator:
    """룰만 바꿔 끼우기 쉬운 최소 점수기."""

    def total(self, rows: list[ScoreInput]) -> float:
        return sum(r.raw_value for r in rows)

# 가중치 정책은 별도 Policy 객체로 분리하면
# 전국 단위 확장 시에도 교체 범위가 명확합니다.`;

function buildProactiveGreeting(): CoachMessage {
  return {
    id: "m0",
    role: "assistant",
    badge: "로드맵 연계 질문",
    text:
      "안녕하세요, Daily Mentor입니다. 지금 로드맵에서는 **탄소 배출 룰 기반 계산**과 **IFRS S1/S2 데이터 맵핑**이 한 묶로 보이고 있어요. \"어떤 엔티티까지 공시 스키마에 넣을지\"를 먼저 고정하면, 이후 파이프라인·감사 추적까지 덜 흔들립니다. 오늘은 그 경계부터 같이 짚어볼까요?",
  };
}

function mockReply(userText: string, ctx: CoachAttachedContext | null): CoachMessage {
  const t = userText.toLowerCase();
  const fromChance =
    ctx?.source === "chance" ||
    t.includes("지원") ||
    t.includes("강점") ||
    t.includes("부족");

  if (fromChance) {
    return {
      id: uid(),
      role: "assistant",
      text:
        "좋은 공고예요. 지금 역량 스냅샷 기준으로 보면, **FastAPI + PostgreSQL**로 에너지·최적화 도메인 API를 설계해 본 경험과, **ESG 지표를 스키마에 매핑**해 본 흔적은 ‘파이프라인 구축’ 요구에 바로 연결됩니다. 포트폴리오에서는 IFRS S1/S2 흐름을 전면에 두세요.\n\n보완으로는 공고가 강조하는 **대용량·쿼리 성능**입니다. 로드맵의 ‘룰 기반 계산 엔진’에서 트래픽이 몰렸을 때 **인덱싱·배치·캐시**를 어떻게 잡았는지 로그로 남겨 두면 면접 때 강한 근거가 됩니다. 오늘 그 부분 리뷰할까요?",
    };
  }

  if (
    ctx?.source === "roadmap" ||
    t.includes("룰") ||
    t.includes("규칙") ||
    t.includes("합산") ||
    t.includes("계산")
  ) {
    return {
      id: uid(),
      role: "assistant",
      badge: "기술 스니펫",
      text:
        "추론 모델 대신 룰 기반을 택한 건 **의사결정 속도·감사 가능성** 측면에서 좋은 선택이에요. FastAPI에서는 ‘점수 계산기’를 독립 모듈로 두고, 정책(가중치·상한)만 바꿔 끼우는 구조가 깔끔합니다. 아래 스니펫을 우측 **Insight Wallet**에 저장해 두었다가 로드맵 아카이브에 옮겨 적어 보세요.",
      code: PYTHON_SNIPPET,
    };
  }

  return {
    id: uid(),
    role: "assistant",
    text:
      "맥락(로드맵·공고)과 연결해서 답할게요. 구체적으로 어떤 출력(공시 필드, 내부 리포트, API 응답)까지를 목표로 하는지 한 줄만 더 알려주세요.",
  };
}

export function CoachView() {
  const formId = useId();
  const endRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [attached, setAttached] = useState<CoachAttachedContext | null>(
    DEMO_ATTACHED_CONTEXTS.roadmap
  );
  const [messages, setMessages] = useState<CoachMessage[]>(() => [buildProactiveGreeting()]);
  const [wallet, setWallet] = useState<CoachWalletItem[]>([]);
  const [sheetOpen, setSheetOpen] = useState(false);

  const scrollBottom = useCallback(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollBottom();
  }, [messages, isLoading, scrollBottom]);

  const addToWallet = useCallback((msg: CoachMessage) => {
    const body = [msg.text, msg.code ? `\n\n\`\`\`python\n${msg.code}\n\`\`\`` : ""]
      .filter(Boolean)
      .join("");
    const item: CoachWalletItem = {
      id: uid(),
      title: `코치 스니펫 · ${msg.badge ?? "응답"}`,
      body,
      createdAt: Date.now(),
    };
    setWallet((w) => [item, ...w]);
  }, []);

  const copyWallet = (id: string) => {
    const item = wallet.find((w) => w.id === id);
    if (item) void navigator.clipboard.writeText(item.body);
  };

  const removeWallet = (id: string) => {
    setWallet((w) => w.filter((x) => x.id !== id));
  };

  const send = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    setMessages((m) => [...m, { id: uid(), role: "user", text }]);
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 520));
    const reply = mockReply(text, attached);
    setMessages((m) => [...m, reply]);
    setIsLoading(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="mx-auto w-full space-y-4 px-0 sm:px-1">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">AI 코치</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
            Daily Mentor — 로드맵·찬스에서 가져온 맥락을 공유하고, 오른쪽 지갑에 스니펫을 쌓아
            실행로 이어갑니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setAttached(DEMO_ATTACHED_CONTEXTS.chance)}
            className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            데모: 찬스 공고
          </button>
          <button
            type="button"
            onClick={() => setAttached(DEMO_ATTACHED_CONTEXTS.roadmap)}
            className="rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-800 shadow-sm hover:bg-indigo-100 dark:border-indigo-900/40 dark:bg-indigo-900/20 dark:text-indigo-300 dark:hover:bg-indigo-900/35"
          >
            데모: 로드맵 스프린트
          </button>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,13fr)_minmax(280px,7fr)] lg:items-stretch">
        {/* 좌: 대화 캔버스 */}
        <section className="flex min-h-[min(72vh,680px)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <div className="border-b border-slate-100 bg-[#F8FAFC] px-4 py-2.5 dark:border-slate-700 dark:bg-slate-900">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-500">
              Interactive Chat Zone
            </p>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`relative max-w-[92%] sm:max-w-[85%] ${
                    m.role === "user"
                      ? "rounded-2xl rounded-tr-md bg-indigo-600 px-4 py-3 text-sm text-white shadow-sm"
                      : "rounded-2xl rounded-tl-md bg-slate-100 px-4 pb-9 pt-3 text-sm text-slate-900 shadow-sm pr-10 dark:bg-slate-900 dark:text-slate-100"
                  }`}
                >
                  {m.role === "assistant" && m.badge ? (
                    <span className="mb-2 inline-block rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-800 ring-1 ring-indigo-200/80">
                      {m.badge}
                    </span>
                  ) : null}
                  <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
                  {m.code ? (
                    <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-900/95 p-3 font-mono text-[11px] leading-relaxed text-emerald-100 ring-1 ring-slate-700">
                      <code>{m.code}</code>
                    </pre>
                  ) : null}
                  {m.role === "assistant" ? (
                    <button
                      type="button"
                      onClick={() => addToWallet(m)}
                      className="absolute bottom-2 right-2 rounded-lg border border-slate-200/80 bg-white/90 p-1.5 text-slate-600 shadow-sm hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-indigo-700 dark:hover:text-indigo-300"
                      title="지갑에 저장"
                      aria-label="지갑에 저장"
                    >
                      <Wallet className="h-3.5 w-3.5" />
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
            {isLoading ? (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-slate-100 px-4 py-3 text-xs text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                  응답 작성 중…
                </div>
              </div>
            ) : null}
            <div ref={endRef} />
          </div>

          <div className="border-t border-slate-200 bg-[#F8FAFC] p-3 dark:border-slate-700 dark:bg-slate-900">
            {attached ? (
              <div className="mb-2 flex items-start gap-2 rounded-xl border-l-4 border-indigo-500 bg-slate-50 px-3 py-2.5 shadow-sm ring-1 ring-slate-200/60 dark:bg-slate-800 dark:ring-slate-700">
                <Paperclip className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-500">
                    맥락 지시자
                  </p>
                  <p className="text-xs font-medium leading-snug text-slate-800 dark:text-slate-200">{attached.label}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setAttached(null)}
                  className="rounded-lg p-1 text-slate-500 hover:bg-slate-200/80 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-slate-200"
                  aria-label="맥락 닫기"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : null}

            <form
              className="flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm ring-1 ring-slate-900/5 focus-within:border-indigo-300 focus-within:ring-indigo-500/15 dark:border-slate-700 dark:bg-slate-800"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <label htmlFor={`${formId}-coach-input`} className="sr-only">
                메시지 입력
              </label>
              <input
                id={`${formId}-coach-input`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="예: 룰 기반으로 점수 합산 구조를 깔끔하게 잡고 싶어요"
                disabled={isLoading}
                className="min-h-[44px] flex-1 rounded-lg border-0 bg-transparent px-2 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-0 dark:text-slate-100 dark:placeholder:text-slate-500"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="inline-flex h-10 shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-3 text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-40"
                aria-label="전송"
              >
                <SendHorizonal className="h-4 w-4" />
              </button>
            </form>
          </div>
        </section>

        {/* 우: 데스크톱 지갑 */}
        <aside className="hidden min-h-0 lg:flex lg:flex-col">
          <InsightWalletPanel
            activeFocusTitle={COACH_ACTIVE_FOCUS.title}
            activeFocusSubtitle={COACH_ACTIVE_FOCUS.subtitle}
            activeFocusBody={COACH_ACTIVE_FOCUS.body}
            activeTags={COACH_ACTIVE_FOCUS.tags}
            wallet={wallet}
            onCopy={copyWallet}
            onRemove={removeWallet}
          />
        </aside>
      </div>

      {/* 모바일 FAB + 바텀시트 */}
      <button
        type="button"
        onClick={() => setSheetOpen(true)}
        className="fixed bottom-20 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg ring-2 ring-white/90 transition hover:bg-indigo-700 lg:hidden"
        aria-label="맥락 및 지갑 열기"
      >
        <Sparkles className="h-6 w-6" />
      </button>

      <AnimatePresence>
        {sheetOpen ? (
          <>
            <motion.button
              type="button"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              aria-label="시트 닫기"
              className="fixed inset-0 z-40 bg-slate-900/40 lg:hidden"
              onClick={() => setSheetOpen(false)}
            />
            <motion.div
              role="dialog"
              aria-modal="true"
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 320 }}
              className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-hidden rounded-t-3xl border border-slate-200 bg-[#F8FAFC] shadow-2xl lg:hidden dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex justify-center border-b border-slate-200 py-2 dark:border-slate-700">
                <span className="h-1 w-10 rounded-full bg-slate-300 dark:bg-slate-600" />
              </div>
              <div className="max-h-[calc(85vh-40px)] overflow-y-auto p-4">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-bold text-slate-900 dark:text-slate-100">맥락 &amp; 지갑</p>
                  <button
                    type="button"
                    onClick={() => setSheetOpen(false)}
                    className="rounded-lg p-2 text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-slate-800"
                    aria-label="닫기"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <InsightWalletPanel
                  activeFocusTitle={COACH_ACTIVE_FOCUS.title}
                  activeFocusSubtitle={COACH_ACTIVE_FOCUS.subtitle}
                  activeFocusBody={COACH_ACTIVE_FOCUS.body}
                  activeTags={COACH_ACTIVE_FOCUS.tags}
                  wallet={wallet}
                  onCopy={copyWallet}
                  onRemove={removeWallet}
                />
              </div>
            </motion.div>
          </>
        ) : null}
      </AnimatePresence>

      <p className="pb-16 text-center text-[11px] text-slate-500 lg:pb-0 dark:text-slate-500">
        목업 응답입니다. 키워드 예: 「지원·강점」→ 찬스 시나리오 / 「룰·합산·계산」→ 기술 스니펫
      </p>
    </div>
  );
}
