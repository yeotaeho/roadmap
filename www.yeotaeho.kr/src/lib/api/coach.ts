// AI 코치 SSE 스트리밍 클라이언트 — fetch ReadableStream 으로 토큰 수신(axios 미사용)
import { getStore } from '@/store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * 코치 응답을 SSE 로 스트리밍한다. 토큰마다 onDelta 를 호출한다.
 * 완료 시 정상 반환, 네트워크/HTTP 오류 시 throw.
 */
export async function streamCoach(
  message: string,
  onDelta: (text: string) => void,
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
    body: JSON.stringify({ message }),
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
        const obj = JSON.parse(raw) as { type?: string; content?: string };
        if (obj.type === 'delta' && obj.content) onDelta(obj.content);
        if (obj.type === 'error') throw new Error('coach stream error');
      } catch {
        /* 파싱 불가 조각 무시 */
      }
    }
  }
}
