'use client';

import { useEffect } from 'react';
import { initializeAuth } from '@/services/silentRefresh';
import { getStore } from '@/store';

/**
 * 앱 초기화 컴포넌트
 * - 인증 상태 복원
 * - Silent Refresh 시작
 */
export function AuthInitializer() {
  useEffect(() => {
    // 앱 시작 시 인증 상태 복원 및 Silent Refresh 시작
    // 성공/실패와 무관하게 복원 시도가 끝나면 resolved 마킹 (HomeGate 분기용)
    initializeAuth().finally(() => {
      getStore().getState().setAuthResolved();
    });
  }, []);

  return null; // UI 렌더링 없음
}

