import { SliceCreator, AuthSlice } from '../types';
import { scheduleSilentRefresh, stopSilentRefresh } from '@/services/silentRefresh';
import { apiClient } from '@/lib/api/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Auth Slice
 * 인증 관련 상태 및 액션을 관리하는 Slice
 */
export const createAuthSlice: SliceCreator<AuthSlice> = (set, get) => ({
  token: null,
  isAuthenticated: false,

  /**
   * 로그인
   * 토큰을 저장하고 인증 상태를 true로 설정
   * Silent Refresh 시작
   */
  login: (token: string) => {
    set(
      {
        token,
        isAuthenticated: true,
      },
      false, // replace 옵션
      'auth/login' // DevTools 액션 이름
    );
    // Silent Refresh 시작
    scheduleSilentRefresh(token);
  },

  /**
   * 로그아웃 (동기)
   * 토큰을 제거하고 인증 상태를 false로 설정
   * 유저 프로필도 함께 초기화
   * Silent Refresh 중지
   * 주의: 백엔드 API 호출 없이 로컬 상태만 초기화합니다.
   */
  logout: () => {
    // Silent Refresh 중지
    stopSilentRefresh();
    
    set(
      {
        token: null,
        isAuthenticated: false,
      },
      false,
      'auth/logout'
    );
    // 다른 Slice 상태도 리셋
    get().clearProfile();
  },

  /**
   * 로그아웃 (비동기)
   * 백엔드 API를 호출하여 리프레시 토큰을 무효화하고
   * 로컬 상태(액세스 토큰)도 함께 제거합니다.
   */
  logoutAsync: async () => {
    try {
      // 백엔드 로그아웃 API 호출 (리프레시 토큰 무효화)
      await apiClient.post(`${API_BASE_URL}/api/oauth/logout`);
    } catch (error) {
      // API 호출 실패해도 로컬 상태는 초기화 (네트워크 오류 등 대비)
      console.error('로그아웃 API 호출 실패:', error);
    } finally {
      // 백엔드 호출 성공 여부와 관계없이 로컬 상태 초기화
      get().logout();
    }
  },

  /**
   * 토큰 설정
   * 토큰이 있으면 인증 상태를 true로, 없으면 false로 설정
   * Silent Refresh 시작/중지
   */
  setToken: (token: string | null) => {
    set(
      {
        token,
        isAuthenticated: !!token,
      },
      false,
      'auth/setToken'
    );
    
    // 토큰이 있으면 Silent Refresh 시작, 없으면 중지
    if (token) {
      scheduleSilentRefresh(token);
    } else {
      stopSilentRefresh();
    }
  },
});

