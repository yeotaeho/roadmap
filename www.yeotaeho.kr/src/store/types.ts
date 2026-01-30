import { StateCreator } from 'zustand';

// ============================================
// 도메인 모델
// ============================================

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

export interface ModalState {
  isOpen: boolean;
  data?: unknown;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

// ============================================
// Slice 인터페이스
// ============================================

/**
 * Auth Slice
 * 인증 관련 상태 및 액션
 */
export interface AuthSlice {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
  logoutAsync: () => Promise<void>;
  setToken: (token: string | null) => void;
}

/**
 * User Slice
 * 유저 프로필 관련 상태 및 액션
 */
export interface UserSlice {
  profile: UserProfile | null;
  isLoading: boolean;
  error: string | null;
  setProfile: (profile: UserProfile) => void;
  updateProfile: (data: Partial<UserProfile>) => void;
  clearProfile: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

/**
 * UI Slice
 * UI 관련 상태 및 액션 (테마, 모달, 토스트 등)
 */
export interface UISlice {
  theme: 'light' | 'dark';
  modals: Record<string, ModalState>;
  toasts: Toast[];
  globalLoading: boolean;
  setTheme: (theme: 'light' | 'dark') => void;
  openModal: (id: string, data?: unknown) => void;
  closeModal: (id: string) => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  setGlobalLoading: (loading: boolean) => void;
}

// ============================================
// Global Store State
// ============================================

/**
 * 전역 Store State
 * 모든 Slice를 통합한 타입
 */
export type StoreState = AuthSlice & UserSlice & UISlice;

// ============================================
// Slice Creator 타입
// ============================================

/**
 * Slice Creator 타입
 * TypeScript 타입 추론을 위한 헬퍼 타입
 */
export type SliceCreator<T> = StateCreator<
  StoreState,
  [['zustand/devtools', never]],
  [],
  T
>;

