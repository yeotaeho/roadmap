'use client';

import { useEffect } from 'react';
import { initializeAuth } from '@/services/silentRefresh';

/**
 * 앱 초기화 컴포넌트
 * - 인증 상태 복원
 * - Silent Refresh 시작
 */
export function AuthInitializer() {
  useEffect(() => {
    // 앱 시작 시 인증 상태 복원 및 Silent Refresh 시작
    initializeAuth();
  }, []);

  return null; // UI 렌더링 없음
}

