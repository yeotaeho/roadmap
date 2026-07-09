// AI 코치 대화 화면(최소) — SSE 스트리밍 + tool 활동 인디케이터
"use client";

import { SendHorizonal } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createNewCoachSession, fetchCoachMessages, streamCoach } from "@/lib/api/coach";
import { useStore } from "@/store";
import { ChatMarkdown } from "@/components/common/ChatMarkdown";
import { useCoachNav } from "./CoachNavContext";

type CoachMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const GREETING: CoachMessage = {
  id: "m0",
  role: "assistant",
  text:
    "안녕하세요, AI 코치입니다. 상담실에서 파악한 성향과 시장 데이터를 근거로 진로 방향과 기회를 함께 판단해 드려요. 어떤 고민부터 볼까요?",
};

export function CoachView() {
  const endRef = useRef<HTMLDivElement>(null);
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const [messages, setMessages] = useState<CoachMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [toolActivity, setToolActivity] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState(false);
  const { sessionId, navToken, adoptSession, refreshSessions } = useCoachNav();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, toolActivity]);

  // navToken 변화(네비게이션)에만 히스토리 로드 — 전송 중 세션 채택은 재로드하지 않음.
  useEffect(() => {
    if (!isAuthenticated) {
      setMessages([GREETING]);
      setToolActivity(null);
      setSessionError(false);
      return;
    }
    let cancelled = false;
    setMessages([GREETING]);
    setToolActivity(null);
    setSessionError(false);
    if (!sessionId) return; // 새 채팅(빈 세션) — 인사말만.
    (async () => {
      try {
        const msgs = await fetchCoachMessages(sessionId);
        if (cancelled) return;
        if (msgs.length > 0) {
          setMessages(msgs.map((m) => ({ id: uid(), role: m.role, text: m.content })));
        }
      } catch {
        /* 히스토리 로드 실패는 대화를 막지 않는다. */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navToken, isAuthenticated]);

  const send = useCallback(async () => {
    const message = input.trim();
    if (!message || isLoading || !isAuthenticated) return;
    let sid = sessionId;
    if (!sid) {
      sid = await createNewCoachSession();
      if (!sid) {
        setSessionError(true);
        return;
      }
      adoptSession(sid); // navToken 미증가 — 아래 낙관적 메시지 유지.
    }
    setInput("");
    setIsLoading(true);
    const assistantId = uid();
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: "user", text: message },
      { id: assistantId, role: "assistant", text: "" },
    ]);
    const appendDelta = (text: string) =>
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + text } : m)),
      );
    try {
      await streamCoach(sid, message, {
        onDelta: (t) => {
          setToolActivity(null);
          appendDelta(t);
        },
        onToolCall: (_name, label) => setToolActivity(label),
        onToolResult: () => setToolActivity(null),
        onError: (msg) => appendDelta(`\n(${msg})`),
      });
    } catch {
      appendDelta("\n(연결에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.)");
    } finally {
      setToolActivity(null);
      setIsLoading(false);
      void refreshSessions(); // 새 세션 제목이 목록에 나타나도록 갱신.
    }
  }, [input, isLoading, isAuthenticated, sessionId, adoptSession, refreshSessions]);

  return (
    <div className="mx-auto w-full">
      <section className="flex h-[calc(100vh-220px)] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {!isAuthenticated && (
            <p className="text-sm text-muted-foreground">로그인하면 코치와 대화를 시작할 수 있어요.</p>
          )}
          {sessionError && (
            <p className="text-sm text-destructive">세션을 열지 못했어요. 새로고침 후 다시 시도해 주세요.</p>
          )}
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <div
                className={
                  m.role === "user"
                    ? "max-w-[80%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground"
                    : "max-w-[80%] rounded-2xl bg-muted px-4 py-2.5 text-sm text-foreground"
                }
              >
                {m.role === "assistant" ? (
                  m.text ? (
                    <ChatMarkdown>{m.text}</ChatMarkdown>
                  ) : (
                    isLoading ? "…" : ""
                  )
                ) : (
                  m.text
                )}
              </div>
            </div>
          ))}
          {toolActivity && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
              {toolActivity} 중…
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form
          className="flex items-center gap-2 border-t border-border px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isAuthenticated ? "코치에게 물어보세요…" : "로그인이 필요해요"}
            disabled={!isAuthenticated || isLoading}
            className="flex-1 rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={!isAuthenticated || isLoading || !input.trim()}
            className="rounded-xl bg-primary p-2.5 text-primary-foreground disabled:opacity-40"
            aria-label="전송"
          >
            <SendHorizonal className="h-4 w-4" />
          </button>
        </form>
      </section>
    </div>
  );
}
