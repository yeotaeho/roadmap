import { apiClient } from './client';

/**
 * 사용자 정보 인터페이스
 */
export interface UserInfo {
  id: number;
  name: string | null;
  email: string | null;
  nickname: string | null;
  profileImage: string | null;
  provider: string;
}

/**
 * 현재 로그인한 사용자 정보를 DB에서 가져오기
 * @returns 사용자 정보 또는 null (실패 시)
 */
export const getCurrentUser = async (): Promise<UserInfo | null> => {
  try {
    const response = await apiClient.get<UserInfo>('/api/oauth/me');
    return response.data;
  } catch (error: any) {
    console.error('사용자 정보 조회 실패:', error);
    // 401 에러는 인증 문제이므로 null 반환
    if (error.response?.status === 401 || error.response?.status === 404) {
      return null;
    }
    // 기타 에러도 null 반환 (fallback 처리)
    return null;
  }
};

/**
 * 프로필 업데이트 요청 인터페이스
 */
export interface UpdateProfileRequest {
  name?: string;
  profileImage?: string;
}

/**
 * 현재 로그인한 사용자 프로필 정보 업데이트
 * @param data 업데이트할 정보 (name, profileImage)
 * @returns 업데이트된 사용자 정보 또는 null (실패 시)
 */
export const updateUserProfile = async (data: UpdateProfileRequest): Promise<UserInfo | null> => {
  try {
    console.log('[API 클라이언트] PUT /api/oauth/me 요청 시작');
    console.log('[API 클라이언트] 요청 데이터:', data);
    console.log('[API 클라이언트] 서버 URL:', process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000');
    
    const response = await apiClient.put<UserInfo>('/api/oauth/me', data);
    
    console.log('[API 클라이언트] 서버 응답 수신 성공');
    console.log('[API 클라이언트] 응답 상태 코드:', response.status);
    console.log('[API 클라이언트] 응답 데이터:', response.data);
    
    return response.data;
  } catch (error: any) {
    console.error('[API 클라이언트] 프로필 업데이트 실패:', error);
    console.error('[API 클라이언트] 에러 상태 코드:', error.response?.status);
    console.error('[API 클라이언트] 에러 메시지:', error.response?.data || error.message);
    if (error.response?.status === 401 || error.response?.status === 404) {
      return null;
    }
    return null;
  }
};

/**
 * 프로필 이미지 파일 업로드
 * @param file 업로드할 이미지 파일
 * @returns 업로드된 이미지 URL 또는 null (실패 시)
 */
export const uploadProfileImage = async (file: File): Promise<string | null> => {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<{ url: string; filename: string }>(
      '/api/user/me/profile-image',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return response.data.url;
  } catch (error: any) {
    console.error('프로필 이미지 업로드 실패:', error);
    return null;
  }
};
