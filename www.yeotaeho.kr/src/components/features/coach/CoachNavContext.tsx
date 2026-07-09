"use client";

// 코치 사이드바(셸)와 CoachView 가 공유하는 세션 상태 Context — 세션 목록·전환·새 채팅.

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  createCoachSession,
  listCoachSessions,
  type SessionSummary,
} from "@/lib/api/coach";
import { useStore } from "@/store";

interface CoachNavValue {
  sessionId: string | null;
  sessions: SessionSummary[];
  navToken: number;
  loadingSessions: boolean;
  selectSession: (id: string) => void;
  startNewChat: () => void;
  adoptSession: (id: string) => void;
  refreshSessions: () => Promise<void>;
}

const CoachNavContext = createContext<CoachNavValue | null>(null);

export function CoachNavProvider({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [navToken, setNavToken] = useState(0);

  const refreshSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      setSessions(await listCoachSessions());
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  // 마운트/인증 전환: 최근 active 세션으로 초기화 + 목록 로드.
  useEffect(() => {
    if (!isAuthenticated) {
      setSessionId(null);
      setSessions([]);
      setNavToken((n) => n + 1); // 뷰가 인사말로 리셋.
      return;
    }
    let cancelled = false;
    (async () => {
      const sid = await createCoachSession(); // get-or-create(최근 active)
      if (cancelled) return;
      setSessionId(sid);
      setNavToken((n) => n + 1); // 뷰가 sid 히스토리 로드.
      await refreshSessions();
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, refreshSessions]);

  const selectSession = useCallback((id: string) => {
    setSessionId(id);
    setNavToken((n) => n + 1);
  }, []);

  const startNewChat = useCallback(() => {
    setSessionId(null);
    setNavToken((n) => n + 1);
  }, []);

  // 전송 중 강제 생성한 세션 채택 — navToken 미증가(히스토리 재로드로 낙관적 메시지를 덮지 않음).
  const adoptSession = useCallback((id: string) => {
    setSessionId(id);
  }, []);

  const value = useMemo(
    () => ({
      sessionId,
      sessions,
      navToken,
      loadingSessions,
      selectSession,
      startNewChat,
      adoptSession,
      refreshSessions,
    }),
    [sessionId, sessions, navToken, loadingSessions, selectSession, startNewChat, adoptSession, refreshSessions],
  );
  return <CoachNavContext.Provider value={value}>{children}</CoachNavContext.Provider>;
}

export function useCoachNav(): CoachNavValue {
  const ctx = useContext(CoachNavContext);
  if (!ctx) throw new Error("useCoachNav must be used within a CoachNavProvider");
  return ctx;
}
