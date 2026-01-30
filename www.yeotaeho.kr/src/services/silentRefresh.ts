import axios from 'axios';
import { getStore } from '@/store';
import { getTokenTimeRemaining, isTokenExpiringSoon } from '@/utils/tokenStorage';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let refreshTimer: NodeJS.Timeout | null = null;

/**
 * 리프레시 토큰으로 액세스 토큰 갱신
 */
const refreshAccessToken = async (): Promise<string | null> => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/api/oauth/refresh`,
      {},
      { withCredentials: true }
    );

    const { accessToken } = response.data;
    
    if (accessToken) {
      getStore().getState().setToken(accessToken);
      return accessToken;
    }
    
    return null;
  } catch (error: any) {
    // 401 에러는 리프레시 토큰이 없거나 만료된 경우 (정상적인 상황)
    // 조용히 처리하고 로그아웃 상태로 전환
    if (error?.response?.status === 401) {
      console.log('리프레시 토큰이 없거나 만료됨 - 로그인 필요');
      getStore().getState().logout();
      return null;
    }
    
    // 그 외의 에러는 로그 출력
    console.error('Silent refresh 실패:', error);
    getStore().getState().logout();
    return null;
  }
};

/**
 * Silent Refresh 스케줄링
 * 토큰 만료 전에 자동으로 리프레시
 */
export const scheduleSilentRefresh = (token: string | null): void => {
  // 기존 타이머 제거
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }

  if (!token) return;

  const timeRemaining = getTokenTimeRemaining(token);
  
  // 이미 만료되었으면 즉시 리프레시
  if (timeRemaining === 0) {
    refreshAccessToken();
    return;
  }

  // 만료 5분 전에 리프레시 (또는 남은 시간의 80% 경과 시)
  const refreshTime = Math.min(
    timeRemaining - (5 * 60 * 1000), // 5분 전
    timeRemaining * 0.8 // 또는 남은 시간의 80%
  );

  // 최소 1분 후에 리프레시 (너무 자주 리프레시 방지)
  const minRefreshTime = Math.max(refreshTime, 60 * 1000);

  console.log(`Silent refresh 예약: ${Math.round(minRefreshTime / 1000)}초 후`);

  refreshTimer = setTimeout(async () => {
    const newToken = await refreshAccessToken();
    
    // 새 토큰으로 다시 스케줄링
    if (newToken) {
      scheduleSilentRefresh(newToken);
    }
  }, minRefreshTime);
};

/**
 * Silent Refresh 중지
 */
export const stopSilentRefresh = (): void => {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
};

/**
 * 앱 초기 로드 시 인증 상태 복원 및 Silent Refresh 시작
 */
export const initializeAuth = async (): Promise<boolean> => {
  try {
    const currentToken = getStore().getState().token;
    
    // 토큰이 있고 아직 유효하면 Silent Refresh 시작
    if (currentToken && !isTokenExpiringSoon(currentToken)) {
      scheduleSilentRefresh(currentToken);
      return true;
    }
    
    // 토큰이 없거나 곧 만료되면 리프레시 토큰으로 갱신 시도
    const newToken = await refreshAccessToken();
    
    if (newToken) {
      scheduleSilentRefresh(newToken);
      return true;
    }
    
    // 리프레시 토큰이 없거나 만료된 경우 (로그인하지 않은 상태)
    // 정상적인 상황이므로 false 반환 (에러 아님)
    return false;
  } catch (error) {
    // 예상치 못한 에러 발생 시에도 조용히 처리
    console.error('인증 초기화 중 오류:', error);
    return false;
  }
};

