import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { createAuthSlice } from './slices/authSlice';
import { createUserSlice } from './slices/userSlice';
import { createUISlice } from './slices/uiSlice';
import { StoreState } from './types';

/**
 * 전역 단일 Store
 * - Zustand를 사용한 중앙 집중식 상태 관리
 * - DevTools: Redux DevTools로 디버깅 지원
 * - Next.js SSR 완벽 호환: 클라이언트에서만 초기화
 * 
 * Note: 새로고침 시 상태가 초기화됩니다.
 * 로그인 상태 유지가 필요하면 서버 세션 또는 HTTP-only 쿠키를 사용하세요.
 */

// 클라이언트에서만 store 생성
let store: ReturnType<typeof createStore> | undefined;

function createStore() {
  return create<StoreState>()(
    devtools(
      (...a) => ({
        ...createAuthSlice(...a),
        ...createUserSlice(...a),
        ...createUISlice(...a),
      }),
      {
        name: 'AppStore', // DevTools에서 표시될 이름
        enabled: process.env.NODE_ENV === 'development', // 개발 환경에서만 활성화
      }
    )
  );
}

// 클라이언트에서만 store 초기화
export const useStore = <T = StoreState>(
  selector?: (state: StoreState) => T
): T => {
  // 서버에서는 기본값 반환
  if (typeof window === 'undefined') {
    if (selector) {
      // selector가 있으면 기본 상태로 selector 실행
      const defaultState: StoreState = {
        token: null,
        isAuthenticated: false,
        login: () => {},
        logout: () => {},
        logoutAsync: async () => {},
        setToken: () => {},
        profile: null,
        isLoading: false,
        error: null,
        setProfile: () => {},
        updateProfile: () => {},
        clearProfile: () => {},
        setLoading: () => {},
        setError: () => {},
        theme: 'light',
        modals: {},
        toasts: [],
        globalLoading: false,
        setTheme: () => {},
        openModal: () => {},
        closeModal: () => {},
        addToast: () => {},
        removeToast: () => {},
        setGlobalLoading: () => {},
      };
      return selector(defaultState) as T;
    }
    return {} as T;
  }
  
  // 클라이언트에서만 store 초기화
  if (!store) {
    store = createStore();
  }
  
  return selector ? store(selector) : (store() as T);
};

/**
 * Store 인스턴스 직접 접근 (getState, setState 등 사용 가능)
 * 컴포넌트 외부에서 store에 접근할 때 사용
 */
export const getStore = () => {
  if (typeof window === 'undefined') {
    // 서버에서는 기본 store 반환 (getState는 사용 가능하지만 실제 상태는 없음)
    return createStore();
  }
  
  if (!store) {
    store = createStore();
  }
  
  return store;
};

// Named exports for convenience
export * from './types';
export { createAuthSlice } from './slices/authSlice';
export { createUserSlice } from './slices/userSlice';
export { createUISlice } from './slices/uiSlice';

