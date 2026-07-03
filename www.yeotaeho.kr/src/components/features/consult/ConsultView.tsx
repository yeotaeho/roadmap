"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Paperclip,
  SendHorizonal,
  Sparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  DEMO_ATTACHED_CONTEXTS,
  type CoachAttachedContext,
} from "@/data/coachContext";
import {
  createConsultSession,
  fetchConsultMessages,
  streamConsult,
} from "@/lib/api/consult";
import { useStore } from "@/store";
import { SelfModelPanel } from "./SelfModelPanel";

type ConsultMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  code?: string;
  badge?: string;
};

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function buildProactiveGreeting(): ConsultMessage {
  return {
    id: "m0",
    role: "assistant",
    badge: "자기이해 탐색",
    text:
      "안녕하세요, AI 상담사입니다. 오늘은 성격·성향·가치관을 함께 들여다보며, 스스로 아직 알아차리지 못한 강점을 찾아보려고 해요. 최근 유독 몰입했던 순간이나 마음에 걸렸던 선택이 있다면, 그 이야기부터 들려주실래요?",
  };
}

const INITIAL_MESSAGES: ConsultMessage[] = [buildProactiveGreeting()];

export function ConsultView() {
  const formId = useId();
  const endRef = useRef<HTMLDivElement>(null);
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [attached, setAttached] = useState<CoachAttachedContext | null>(null);
  const [messages, setMessages] = useState<ConsultMessage[]>(() => INITIAL_MESSAGES);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const sessionIdRef = useRef<string | null>(null);

  const scrollBottom = useCallback(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollBottom();
  }, [messages, isLoading, scrollBottom]);

  // 로그인 상태에서 마운트 시 세션 재개(get-or-create) + 기존 히스토리 로드
  useEffect(() => {
    if (!isAuthenticated) {
      sessionIdRef.current = null;
      setSessionId(null);
      setMessages(INITIAL_MESSAGES);
      return;
    }
    let cancelled = false;
    setSessionError(false);
    (async () => {
      try {
        const id = await createConsultSession();
        if (cancelled) return;
        if (!id) {
          setSessionError(true);
          return;
        }
        const history = await fetchConsultMessages(id);
        if (cancelled) return;
        if (history.length > 0) {
          setMessages(
            history.map((h) => ({ id: uid(), role: h.role, text: h.content })),
          );
        }
        sessionIdRef.current = id;
        setSessionId(id);
      } catch {
        if (!cancelled) setSessionError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, retryKey]);

  const send = async () => {
    const text = input.trim();
    if (!text || isLoading || !sessionId) return;
    setInput("");
    setMessages((m) => [...m, { id: uid(), role: "user", text }]);
    const assistantId = uid();
    setMessages((m) => [...m, { id: assistantId, role: "assistant", text: "" }]);
    setIsLoading(true);
    try {
      await streamConsult(sessionId, text, (delta) => {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === assistantId ? { ...msg, text: msg.text + delta } : msg,
          ),
        );
      });
    } catch {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === assistantId && !msg.text
            ? { ...msg, text: "상담 응답을 불러오지 못했어요. 로그인 상태를 확인하고 다시 시도해 주세요." }
            : msg,
        ),
      );
    } finally {
      setIsLoading(false);
    }
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
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">AI 상담</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
            AI 상담사 — 대화를 통해 나의 성향과 강점을 함께 발견해요. 대화가 쌓이면 오른쪽에
            나의 성향이 정리돼요.
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
                      : "rounded-2xl rounded-tl-md bg-slate-100 px-4 py-3 text-sm text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100"
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
              <label htmlFor={`${formId}-consult-input`} className="sr-only">
                메시지 입력
              </label>
              <input
                id={`${formId}-consult-input`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  isAuthenticated
                    ? "예: 룰 기반으로 점수 합산 구조를 깔끔하게 잡고 싶어요"
                    : "로그인 후 AI 상담사와 대화할 수 있어요"
                }
                disabled={isLoading || !sessionId}
                className="min-h-[44px] flex-1 rounded-lg border-0 bg-transparent px-2 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-0 dark:text-slate-100 dark:placeholder:text-slate-500"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim() || !sessionId}
                className="inline-flex h-10 shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-3 text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-40"
                aria-label="전송"
              >
                <SendHorizonal className="h-4 w-4" />
              </button>
            </form>
            {isAuthenticated && !sessionId && sessionError ? (
              <button
                type="button"
                onClick={() => setRetryKey((k) => k + 1)}
                className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                대화 세션 연결 실패 · 다시 시도
              </button>
            ) : null}
          </div>
        </section>

        {/* 우: 데스크톱 성향 패널 */}
        <aside className="hidden min-h-0 lg:flex lg:flex-col">
          <SelfModelPanel />
        </aside>
      </div>

      {/* 모바일 FAB + 바텀시트 */}
      <button
        type="button"
        onClick={() => setSheetOpen(true)}
        className="fixed bottom-20 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg ring-2 ring-white/90 transition hover:bg-indigo-700 lg:hidden"
        aria-label="나의 성향 열기"
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
                  <p className="text-sm font-bold text-slate-900 dark:text-slate-100">나의 성향</p>
                  <button
                    type="button"
                    onClick={() => setSheetOpen(false)}
                    className="rounded-lg p-2 text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-slate-800"
                    aria-label="닫기"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <SelfModelPanel />
              </div>
            </motion.div>
          </>
        ) : null}
      </AnimatePresence>

      <p className="pb-16 text-center text-[11px] text-slate-500 lg:pb-0 dark:text-slate-500">
        {isAuthenticated
          ? "AI 상담사와의 대화는 세션 단위로 저장됩니다."
          : "로그인 후 AI 상담사와 대화하고 세션 히스토리를 이어갈 수 있어요."}
      </p>
    </div>
  );
}
