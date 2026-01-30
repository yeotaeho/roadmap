/**
 * API 응답의 ISO 날짜 문자열을 Date 객체로 변환
 * superjson을 사용하지 않을 때 대안
 */
export function parseApiDates<T>(data: T): T {
  if (data === null || data === undefined) return data;

  // ISO 8601 날짜 문자열 패턴
  if (typeof data === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(data)) {
    return new Date(data) as unknown as T;
  }

  // 배열 처리
  if (Array.isArray(data)) {
    return data.map(parseApiDates) as unknown as T;
  }

  // 객체 처리
  if (typeof data === 'object') {
    return Object.fromEntries(
      Object.entries(data).map(([key, value]) => [key, parseApiDates(value)])
    ) as T;
  }

  return data;
}

/**
 * Date 객체를 ISO 문자열로 변환 (서버 전송용)
 */
export function serializeDates<T>(data: T): T {
  if (data === null || data === undefined) return data;

  if (data instanceof Date) {
    return data.toISOString() as unknown as T;
  }

  if (Array.isArray(data)) {
    return data.map(serializeDates) as unknown as T;
  }

  if (typeof data === 'object') {
    return Object.fromEntries(
      Object.entries(data).map(([key, value]) => [key, serializeDates(value)])
    ) as T;
  }

  return data;
}

/**
 * 날짜 포맷팅 유틸리티
 */
export function formatDate(date: Date | string, options?: Intl.DateTimeFormatOptions): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  return dateObj.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    ...options,
  });
}

/**
 * 상대 시간 표시 (예: "3시간 전")
 */
export function formatRelativeTime(date: Date | string): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - dateObj.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return '방금 전';
  if (diffMin < 60) return `${diffMin}분 전`;
  if (diffHour < 24) return `${diffHour}시간 전`;
  if (diffDay < 7) return `${diffDay}일 전`;
  
  return formatDate(dateObj);
}

