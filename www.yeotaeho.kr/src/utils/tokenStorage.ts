/**
 * JWT 토큰 저장 및 관리 유틸리티
 * 
 * 보안 정책:
 * - 액세스 토큰: 메모리(Zustand)에만 저장 (localStorage 사용 안 함)
 * - 리프레시 토큰: HttpOnly 쿠키에 저장 (백엔드에서 설정)
 */

/**
 * JWT 토큰 저장 (더 이상 사용하지 않음 - Zustand store에 직접 저장)
 * @deprecated localStorage 저장을 제거했으므로 이 함수는 사용하지 않습니다.
 * 대신 Zustand store의 login() 또는 setToken() 메서드를 사용하세요.
 */
export const saveToken = (token: string): void => {
    // localStorage 저장 제거 - 보안상 메모리(Zustand)에만 저장
    console.log('토큰은 메모리(Zustand)에만 저장됩니다. localStorage는 사용하지 않습니다.');
};

/**
 * 저장된 JWT 토큰 조회 (더 이상 사용하지 않음)
 * @deprecated localStorage에서 조회하지 않으므로 이 함수는 사용하지 않습니다.
 * 대신 Zustand store에서 직접 조회하세요: useStore.getState().token
 */
export const getToken = (): string | null => {
    // localStorage에서 조회하지 않음
    return null;
};

/**
 * 저장된 JWT 토큰 삭제 (더 이상 사용하지 않음)
 * @deprecated localStorage를 사용하지 않으므로 이 함수는 사용하지 않습니다.
 * 대신 Zustand store의 logout() 메서드를 사용하세요.
 */
export const removeToken = (): void => {
    // localStorage 삭제 불필요
    console.log('토큰은 Zustand store에서 관리됩니다.');
};

/**
 * 토큰 존재 여부 확인 (더 이상 사용하지 않음)
 * @deprecated localStorage를 사용하지 않으므로 이 함수는 사용하지 않습니다.
 * 대신 Zustand store의 isAuthenticated를 확인하세요.
 */
export const hasToken = (): boolean => {
    return false;
};

/**
 * JWT 토큰 디코딩 (Base64 디코딩)
 * @param token JWT 토큰 문자열
 * @returns 디코딩된 페이로드 객체 또는 null
 */
export const decodeToken = (token: string): any | null => {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) {
            console.error('Invalid JWT token format');
            return null;
        }

        // JWT 페이로드 (두 번째 부분) 디코딩
        const payload = parts[1];
        const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
        return JSON.parse(decoded);
    } catch (error) {
        console.error('Failed to decode token:', error);
        return null;
    }
};

/**
 * JWT 토큰에서 사용자 이메일 추출
 * @param token JWT 토큰 문자열 (Zustand store에서 가져온 토큰)
 * @returns 사용자 이메일 또는 null
 */
export const getUserEmail = (token: string | null): string | null => {
    if (!token) return null;

    const decoded = decodeToken(token);
    return decoded?.email || null;
};

/**
 * JWT 토큰에서 사용자 이름 추출
 * @param token JWT 토큰 문자열 (Zustand store에서 가져온 토큰)
 * @returns 사용자 이름 또는 null (name이 없으면 null 반환, 이메일은 사용하지 않음)
 */
export const getUserName = (token: string | null): string | null => {
    if (!token) return null;

    const decoded = decodeToken(token);
    // name만 반환 (이메일 fallback 제거)
    return decoded?.name || null;
};

/**
 * JWT 토큰에서 사용자 ID 추출
 * @param token JWT 토큰 문자열 (Zustand store에서 가져온 토큰)
 * @returns 사용자 ID 또는 null
 */
export const getUserId = (token: string | null): string | null => {
    if (!token) return null;

    const decoded = decodeToken(token);
    return decoded?.userId?.toString() || decoded?.sub || null;
};

/**
 * JWT 토큰에서 만료 시간 추출
 * @param token JWT 토큰 문자열
 * @returns 만료 시간 (밀리초), 없으면 null
 */
export const getTokenExpirationTime = (token: string | null): number | null => {
    if (!token) return null;
    
    try {
        const decoded = decodeToken(token);
        if (!decoded?.exp) return null;
        
        // JWT exp는 초 단위이므로 밀리초로 변환
        return decoded.exp * 1000;
    } catch {
        return null;
    }
};

/**
 * 토큰 만료까지 남은 시간 계산
 * @param token JWT 토큰
 * @returns 남은 시간 (밀리초), 만료되었으면 0
 */
export const getTokenTimeRemaining = (token: string | null): number => {
    const expirationTime = getTokenExpirationTime(token);
    if (!expirationTime) return 0;
    
    const now = Date.now();
    const remaining = expirationTime - now;
    
    return remaining > 0 ? remaining : 0;
};

/**
 * 토큰이 곧 만료되는지 확인 (기본 5분 이내)
 * @param token JWT 토큰
 * @param bufferMinutes 버퍼 시간 (분), 기본 5분
 * @returns 만료 임박 여부
 */
export const isTokenExpiringSoon = (
    token: string | null, 
    bufferMinutes: number = 5
): boolean => {
    const remaining = getTokenTimeRemaining(token);
    const bufferMs = bufferMinutes * 60 * 1000;
    
    return remaining > 0 && remaining < bufferMs;
};

