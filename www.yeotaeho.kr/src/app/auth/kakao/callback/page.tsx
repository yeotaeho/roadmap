"use client";

import React, { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useStore';

export default function KakaoCallbackPage() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const { login } = useAuth();
    const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'newUser'>('loading');
    const [message, setMessage] = useState<string>('');
    const [signupToken, setSignupToken] = useState<string>('');

    useEffect(() => {
        const handleCallback = async () => {
            try {
                // URL에서 code 파라미터 추출
                const code = searchParams.get('code');
                const error = searchParams.get('error');

                // 에러가 있는 경우
                if (error) {
                    setStatus('error');
                    setMessage(`인증 오류: ${error}`);
                    console.error('OAuth error:', error);
                    return;
                }

                // code가 없는 경우
                if (!code) {
                    setStatus('error');
                    setMessage('인증 코드를 받지 못했습니다.');
                    console.error('No authorization code received');
                    return;
                }

                // URL에서 state 파라미터도 추출
                const state = searchParams.get('state');

                // 백엔드로 code와 state 전송하여 토큰 교환
                const response = await fetch('http://localhost:8000/api/oauth/kakao/callback', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ code, state }),
                });

                if (response.ok) {
                    const data = await response.json();

                    // 회원가입 완료인 경우 (로그인 안됨)
                    if (data.isSignupComplete) {
                        setStatus('success');
                        setMessage(data.message || '회원가입이 완료되었습니다.');
                        console.log('Signup complete:', data);

                        // localStorage에서 나이와 관심분야 읽어서 백엔드로 전달
                        const signupAge = localStorage.getItem('signup_age');
                        const signupInterests = localStorage.getItem('signup_interests');

                        if (signupAge && signupInterests && data.userId) {
                            try {
                                await fetch('http://localhost:8000/api/oauth/update-signup-info', {
                                    method: 'POST',
                                    credentials: 'include',
                                    headers: {
                                        'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({
                                        userId: data.userId,
                                        age: parseInt(signupAge),
                                        interests: JSON.parse(signupInterests)
                                    }),
                                });

                                // localStorage 정리
                                localStorage.removeItem('signup_age');
                                localStorage.removeItem('signup_interests');
                            } catch (error) {
                                console.error('회원가입 정보 업데이트 실패:', error);
                            }
                        }

                        // 로그인 페이지로 리다이렉트
                        setTimeout(() => {
                            router.push('/login');
                        }, 2000);
                        return;
                    }

                    // 신규 사용자인 경우 경고 메시지 표시
                    if (data.isNewUser) {
                        setStatus('newUser');
                        setMessage('회원가입이 필요합니다.');
                        setSignupToken(data.signupToken || '');
                        console.log('New user detected:', data);
                        return;
                    }

                    // 로그인 완료 처리
                    setStatus('success');
                    setMessage(data.message || '로그인 성공!');
                    console.log('Login successful:', data);

                    // JWT 토큰 저장 (Zustand 메모리에만 저장, localStorage 사용 안 함)
                    if (data.accessToken) {
                        login(data.accessToken); // Zustand store에만 저장
                    }
                    // 리프레시 토큰은 HttpOnly 쿠키로 자동 설정됨 (백엔드에서 처리)

                    // 로그인 성공 후 메인 페이지나 대시보드로 리디렉션
                    setTimeout(() => {
                        router.push('/');
                    }, 2000);
                } else {
                    const errorData = await response.json().catch(() => ({ message: '알 수 없는 오류' }));
                    setStatus('error');
                    setMessage(`로그인 실패: ${errorData.message || response.statusText}`);
                    console.error('Login failed:', errorData);
                }
            } catch (error) {
                setStatus('error');
                const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
                setMessage(`연결 오류: ${errorMessage}`);
                console.error('Error during callback:', error);
            }
        };

        handleCallback();
    }, [searchParams, router, login]);

    const handleSignup = () => {
        const signupParams = new URLSearchParams({
            token: signupToken,
        });
        router.push(`/signup?${signupParams.toString()}`);
    };

    const handleCancel = () => {
        router.push('/login');
    };

    return (
        <div className="min-h-screen bg-white flex items-center justify-center px-4">
            <div className="w-full max-w-md text-center">
                {status === 'loading' && (
                    <>
                        <div className="mb-4">
                            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-yellow-400"></div>
                        </div>
                        <h2 className="text-2xl font-bold text-black mb-2">로그인 처리 중...</h2>
                        <p className="text-gray-600">잠시만 기다려주세요.</p>
                    </>
                )}

                {status === 'success' && (
                    <>
                        <div className="mb-4">
                            <svg className="mx-auto h-12 w-12 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h2 className="text-2xl font-bold text-black mb-2">로그인 성공!</h2>
                        <p className="text-gray-600 mb-4">{message}</p>
                        <p className="text-sm text-gray-500">잠시 후 메인 페이지로 이동합니다...</p>
                    </>
                )}

                {status === 'newUser' && (
                    <>
                        <div className="mb-4">
                            <svg className="mx-auto h-12 w-12 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <h2 className="text-2xl font-bold text-black mb-2">회원가입 필요</h2>
                        <p className="text-gray-600 mb-6">{message}</p>
                        <p className="text-sm text-gray-500 mb-6">회원가입을 진행하시겠습니까?</p>
                        <div className="flex gap-4 justify-center">
                            <button
                                onClick={handleCancel}
                                className="px-6 py-2 border-2 border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition"
                            >
                                취소
                            </button>
                            <button
                                onClick={handleSignup}
                                className="px-6 py-2 bg-black text-white rounded-md hover:bg-gray-800 transition"
                            >
                                회원가입
                            </button>
                        </div>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <div className="mb-4">
                            <svg className="mx-auto h-12 w-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </div>
                        <h2 className="text-2xl font-bold text-black mb-2">로그인 실패</h2>
                        <p className="text-gray-600 mb-4">{message}</p>
                        <button
                            onClick={() => router.push('/login')}
                            className="px-6 py-2 bg-black text-white rounded-md hover:bg-gray-800 transition"
                        >
                            로그인 페이지로 돌아가기
                        </button>
                    </>
                )}
            </div>
        </div>
    );
}

