import { SliceCreator, UserSlice, UserProfile } from '../types';

/**
 * User Slice
 * 유저 프로필 관련 상태 및 액션을 관리하는 Slice
 */
export const createUserSlice: SliceCreator<UserSlice> = (set, get) => ({
  profile: null,
  isLoading: false,
  error: null,

  /**
   * 프로필 설정
   * 유저 프로필 정보를 저장
   */
  setProfile: (profile: UserProfile) => {
    set(
      {
        profile,
        error: null,
      },
      false,
      'user/setProfile'
    );
  },

  /**
   * 프로필 업데이트
   * 기존 프로필 정보를 부분적으로 업데이트
   */
  updateProfile: (data: Partial<UserProfile>) => {
    const currentProfile = get().profile;
    if (currentProfile) {
      set(
        {
          profile: {
            ...currentProfile,
            ...data,
          },
        },
        false,
        'user/updateProfile'
      );
    }
  },

  /**
   * 프로필 초기화
   * 유저 프로필 정보를 제거
   */
  clearProfile: () => {
    set(
      {
        profile: null,
        error: null,
      },
      false,
      'user/clearProfile'
    );
  },

  /**
   * 로딩 상태 설정
   */
  setLoading: (loading: boolean) => {
    set(
      {
        isLoading: loading,
      },
      false,
      'user/setLoading'
    );
  },

  /**
   * 에러 상태 설정
   */
  setError: (error: string | null) => {
    set(
      {
        error,
      },
      false,
      'user/setError'
    );
  },
});

