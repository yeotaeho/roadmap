"use client";

import React, { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useStore';

export default function SignupPage() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const { login } = useAuth();

    // 회원가입 토큰 (URL 파라미터에서 가져옴)
    const signupToken = searchParams.get('token');

    const [isOAuthSignup, setIsOAuthSignup] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [signupStatus, setSignupStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const handleOAuthSignup = async () => {
        if (isProcessing) return;

        setIsProcessing(true);
        setSignupStatus('loading');
        setErrorMessage(null);

        try {
            const response = await fetch('http://localhost:8000/api/oauth/signup', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    signupToken: signupToken || '',
                }),
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Signup successful:', data);
                setSignupStatus('success');

                // JWT 토큰 저장
                if (data.accessToken) {
                    login(data.accessToken);
                }

                // 회원가입 성공 후 메인 페이지로 리디렉션
                setTimeout(() => {
                    router.push('/');
                }, 1500);
            } else {
                const errorData = await response.json().catch(() => ({ message: '알 수 없는 오류' }));
                console.error('Signup failed:', errorData);
                setSignupStatus('error');
                setErrorMessage(errorData.message || response.statusText);
                setIsProcessing(false);
            }
        } catch (error) {
            const msg = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
            console.error('Error during signup:', error);
            setSignupStatus('error');
            setErrorMessage(`연결 오류: ${msg}`);
            setIsProcessing(false);
        }
    };

    useEffect(() => {
        // OAuth 토큰이 있으면 자동 회원가입 처리
        if (signupToken && signupStatus === 'idle') {
            setIsOAuthSignup(true);
            handleOAuthSignup();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [signupToken, signupStatus]);

    // 소셜 로그인 핸들러
    const handleSocialLogin = async (provider: 'kakao' | 'naver' | 'google') => {
        try {
            const response = await fetch(`http://localhost:8000/api/oauth/${provider}/login`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                const redirectUrl = data.authUrl || data.redirectUrl;
                if (redirectUrl) {
                    window.location.href = redirectUrl;
                } else {
                    console.log('Login response:', data);
                    alert('로그인 URL을 받지 못했습니다.');
                }
            } else {
                let errorMessage = `Login failed: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.message || errorData.error || errorMessage;
                } catch (e) {
                    const text = await response.text();
                    if (text) {
                        errorMessage = text;
                    }
                }
                console.error('Login failed:', errorMessage);
                alert(`로그인 실패: ${errorMessage}`);
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
            console.error('Error during social login:', error);
            alert(`연결 오류: ${errorMessage}\n서버가 실행 중인지 확인해주세요.`);
        }
    };

    // OAuth 회원가입 처리 중일 때
    if (isOAuthSignup) {
        return (
            <div className="min-h-screen bg-white flex items-center justify-center px-4">
                <div className="w-full max-w-md text-center">
                    {signupStatus === 'loading' && (
                        <>
                            <div className="mb-4">
                                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-black"></div>
                            </div>
                            <h2 className="text-2xl font-bold text-black mb-2">회원가입 처리 중...</h2>
                            <p className="text-gray-600">잠시만 기다려주세요.</p>
                        </>
                    )}

                    {signupStatus === 'success' && (
                        <>
                            <div className="mb-4">
                                <svg className="mx-auto h-12 w-12 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                            <h2 className="text-2xl font-bold text-black mb-2">회원가입 성공!</h2>
                            <p className="text-gray-600 mb-4">잠시 후 메인 페이지로 이동합니다...</p>
                        </>
                    )}

                    {signupStatus === 'error' && (
                        <>
                            <div className="mb-4">
                                <svg className="mx-auto h-12 w-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </div>
                            <h2 className="text-2xl font-bold text-black mb-2">회원가입 실패</h2>
                            <p className="text-gray-600 mb-4">{errorMessage}</p>
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

    return (
        <div className="min-h-screen bg-white flex items-center justify-center px-4 py-12">
            <div className="w-full max-w-md">
                {/* WELCOME Header */}
                <h1 className="text-4xl font-bold text-black text-center mb-6">WELCOME!</h1>

                {/* Introductory Text */}
                <div className="text-center mb-8 text-gray-700 leading-relaxed">
                    <p className="mb-1">데상트코리아 통합 회원이 되시면 온라인 스토어 및</p>
                    <p>오프라인 매장에서 다양한 혜택이 제공됩니다.</p>
                </div>

                {/* Primary Sign Up Button */}
                <button className="w-full bg-black text-white py-4 rounded-lg font-medium hover:bg-gray-800 transition mb-8 text-lg">
                    회원가입
                </button>

                {/* Divider */}
                <div className="border-t border-gray-300 mb-6"></div>

                {/* Social Login Section */}
                <div className="text-center mb-6">
                    <p className="text-black text-sm">SNS로 시작하기</p>
                </div>

                {/* Social Login Buttons */}
                <div className="flex justify-center items-center space-x-4">
                    {/* Kakao */}
                    <button
                        onClick={() => handleSocialLogin('kakao')}
                        className="w-16 h-16 bg-yellow-400 rounded-full flex items-center justify-center hover:bg-yellow-500 transition shadow-sm cursor-pointer"
                    >
                        <svg className="w-8 h-8 text-black" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 3c5.799 0 10.5 3.664 10.5 8.185 0 4.52-4.701 8.184-10.5 8.184a13.5 13.5 0 0 1-1.727-.11l-4.408 2.883c-.501.265-.678.236-.472-.413l.892-3.678c-2.88-1.46-4.785-3.99-4.785-6.866C1.5 6.665 6.201 3 12 3z" />
                        </svg>
                    </button>

                    {/* Naver */}
                    <button
                        onClick={() => handleSocialLogin('naver')}
                        className="w-16 h-16 bg-green-500 rounded-full flex items-center justify-center hover:bg-green-600 transition shadow-sm cursor-pointer"
                    >
                        <span className="text-white font-bold text-xl">N</span>
                    </button>

                    {/* Google */}
                    <button
                        onClick={() => handleSocialLogin('google')}
                        className="w-16 h-16 bg-white border border-gray-300 rounded-full flex items-center justify-center hover:bg-gray-50 transition shadow-sm cursor-pointer"
                    >
                        <svg className="w-8 h-8" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}
