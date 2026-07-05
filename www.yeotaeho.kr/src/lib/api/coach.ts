// AI 코치 SSE 스트리밍 클라이언트 — delta·tool_call·tool_result 이벤트 수신(fetch ReadableStream)
import { getStore } from '@/store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface CoachApiMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface CoachStreamHandlers {
  onDelta: (text: string) => void;
  onToolCall?: (name: string, label: string) => void;
  onToolResult?: (name: string) => void;
  onError?: (message: string) => void;
}

export async function createCoachSession(): Promise<string | null> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/sessions`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.sessionId ?? null;
}

export async function fetchCoachMessages(sessionId: string): Promise<CoachApiMessage[]> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/sessions/${sessionId}/messages`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data?.messages ?? [];
}

export async function streamCoach(
  sessionId: string,
  message: string,
  handlers: CoachStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getStore().getState().token;
  const res = await fetch(`${API_BASE_URL}/api/coach/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',
    body: JSON.stringify({ sessionId, message }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`coach stream failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? ''; // 마지막 미완성 조각 보존
    for (const evt of events) {
      const dataLine = evt.split('\n').find((l) => l.startsWith('data:'));
      if (!dataLine) continue;
      const raw = dataLine.slice(5).trim();
      if (!raw) continue;
      try {
        const obj = JSON.parse(raw) as {
          type?: string;
          content?: string;
          name?: string;
          label?: string;
          message?: string;
        };
        if (obj.type === 'delta' && obj.content) handlers.onDelta(obj.content);
        if (obj.type === 'tool_call' && obj.name) handlers.onToolCall?.(obj.name, obj.label ?? obj.name);
        if (obj.type === 'tool_result' && obj.name) handlers.onToolResult?.(obj.name);
        if (obj.type === 'error') handlers.onError?.(obj.message ?? '코치 응답 중 오류가 발생했어요.');
      } catch {
        /* 파싱 불가 조각 무시 */
      }
    }
  }
}
