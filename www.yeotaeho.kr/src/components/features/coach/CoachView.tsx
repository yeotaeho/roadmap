// AI 코치 대화 화면(최소) — SSE 스트리밍 + tool 활동 인디케이터
"use client";

import { SendHorizonal, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createCoachSession, fetchCoachMessages, streamCoach } from "@/lib/api/coach";
import { useStore } from "@/store";

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
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, toolActivity]);

  // 로그인 상태에서 세션 재개(get-or-create) + 히스토리 로드
  useEffect(() => {
    if (!isAuthenticated) return;
    (async () => {
      const sid = await createCoachSession();
      if (!sid) {
        setSessionError(true);
        return;
      }
      setSessionId(sid);
      const msgs = await fetchCoachMessages(sid);
      if (msgs.length > 0) {
        setMessages(msgs.map((m) => ({ id: uid(), role: m.role, text: m.content })));
      }
    })();
  }, [isAuthenticated]);

  const send = useCallback(async () => {
    const message = input.trim();
    if (!message || isLoading || !sessionId) return;
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
      await streamCoach(sessionId, message, {
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
    }
  }, [input, isLoading, sessionId]);

  return (
    <div className="mx-auto w-full">
      <section className="flex min-h-[min(72vh,680px)] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <Sparkles className="h-5 w-5 text-primary" aria-hidden />
          <div>
            <h1 className="text-base font-semibold text-foreground">AI 코치</h1>
            <p className="text-xs text-muted-foreground">데이터 근거로 진로 방향·기회·실행을 함께 판단해요.</p>
          </div>
        </header>

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
                    ? "max-w-[80%] rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground"
                    : "max-w-[80%] whitespace-pre-wrap rounded-2xl bg-muted px-4 py-2.5 text-sm text-foreground"
                }
              >
                {m.text || (isLoading ? "…" : "")}
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
            disabled={!isAuthenticated || isLoading || !sessionId}
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
