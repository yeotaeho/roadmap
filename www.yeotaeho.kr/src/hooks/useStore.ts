import { useStore as useZustandStore } from '@/store';
import { StoreState } from '@/store/types';
import { useMemo } from 'react';

/**
 * 선택적 구독을 위한 Custom Hooks
 * 성능 최적화: 필요한 상태만 구독하여 불필요한 리렌더링 방지
 */

// ============================================
// Auth Hooks
// ============================================

/**
 * 인증 관련 상태 및 액션
 */
export const useAuth = () => {
  const token = useZustandStore((state: StoreState) => state.token);
  const isAuthenticated = useZustandStore((state: StoreState) => state.isAuthenticated);
  const login = useZustandStore((state: StoreState) => state.login);
  const logout = useZustandStore((state: StoreState) => state.logout);
  const logoutAsync = useZustandStore((state: StoreState) => state.logoutAsync);
  const setToken = useZustandStore((state: StoreState) => state.setToken);

  return useMemo(
    () => ({
      token,
      isAuthenticated,
      login,
      logout,
      logoutAsync,
      setToken,
    }),
    [token, isAuthenticated, login, logout, logoutAsync, setToken]
  );
};

// ============================================
// User Hooks
// ============================================

/**
 * 유저 프로필 상태
 */
export const useUserProfile = () =>
  useZustandStore((state: StoreState) => state.profile);

/**
 * 유저 프로필 로딩 및 에러 상태
 */
export const useUserStatus = () =>
  useZustandStore((state: StoreState) => ({
    isLoading: state.isLoading,
    error: state.error,
  }));

/**
 * 유저 프로필 액션
 */
export const useUserActions = () =>
  useZustandStore((state: StoreState) => ({
    setProfile: state.setProfile,
    updateProfile: state.updateProfile,
    clearProfile: state.clearProfile,
    setLoading: state.setLoading,
    setError: state.setError,
  }));

// ============================================
// UI Hooks
// ============================================

/**
 * 테마 관련 상태 및 액션
 */
export const useTheme = () =>
  useZustandStore((state: StoreState) => ({
    theme: state.theme,
    setTheme: state.setTheme,
  }));

/**
 * 모달 관련 상태 및 액션
 * @param modalId 모달 ID
 */
export const useModal = (modalId: string) =>
  useZustandStore((state: StoreState) => ({
    isOpen: state.modals[modalId]?.isOpen ?? false,
    data: state.modals[modalId]?.data,
    openModal: (data?: unknown) => state.openModal(modalId, data),
    closeModal: () => state.closeModal(modalId),
  }));

/**
 * 토스트 관련 상태 및 액션
 */
export const useToasts = () =>
  useZustandStore((state: StoreState) => ({
    toasts: state.toasts,
    addToast: state.addToast,
    removeToast: state.removeToast,
  }));

/**
 * 전역 로딩 상태
 */
export const useGlobalLoading = () =>
  useZustandStore((state: StoreState) => ({
    globalLoading: state.globalLoading,
    setGlobalLoading: state.setGlobalLoading,
  }));

