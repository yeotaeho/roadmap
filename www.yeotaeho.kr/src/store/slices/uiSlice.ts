import { SliceCreator, UISlice, Toast } from '../types';

/**
 * UI Slice
 * UI 관련 상태 및 액션을 관리하는 Slice (테마, 모달, 토스트 등)
 */
export const createUISlice: SliceCreator<UISlice> = (set) => ({
  theme: 'light',
  modals: {},
  toasts: [],
  globalLoading: false,

  /**
   * 테마 설정
   */
  setTheme: (theme: 'light' | 'dark') => {
    set(
      {
        theme,
      },
      false,
      'ui/setTheme'
    );
    // localStorage에 저장 (선택사항)
    if (typeof window !== 'undefined') {
      localStorage.setItem('theme', theme);
    }
  },

  /**
   * 모달 열기
   */
  openModal: (id: string, data?: unknown) => {
    set(
      (state) => ({
        modals: {
          ...state.modals,
          [id]: {
            isOpen: true,
            data,
          },
        },
      }),
      false,
      `ui/openModal:${id}`
    );
  },

  /**
   * 모달 닫기
   */
  closeModal: (id: string) => {
    set(
      (state) => {
        const newModals = { ...state.modals };
        if (newModals[id]) {
          newModals[id] = {
            ...newModals[id],
            isOpen: false,
          };
        }
        return { modals: newModals };
      },
      false,
      `ui/closeModal:${id}`
    );
  },

  /**
   * 토스트 추가
   */
  addToast: (toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast: Toast = {
      ...toast,
      id,
      duration: toast.duration ?? 3000,
    };

    set(
      (state) => ({
        toasts: [...state.toasts, newToast],
      }),
      false,
      'ui/addToast'
    );

    // 자동 제거 (duration 후)
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        set(
          (state) => ({
            toasts: state.toasts.filter((t) => t.id !== id),
          }),
          false,
          'ui/removeToast'
        );
      }, newToast.duration);
    }
  },

  /**
   * 토스트 제거
   */
  removeToast: (id: string) => {
    set(
      (state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }),
      false,
      'ui/removeToast'
    );
  },

  /**
   * 전역 로딩 상태 설정
   */
  setGlobalLoading: (loading: boolean) => {
    set(
      {
        globalLoading: loading,
      },
      false,
      'ui/setGlobalLoading'
    );
  },
});

