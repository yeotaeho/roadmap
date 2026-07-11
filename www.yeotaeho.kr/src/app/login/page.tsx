// SNS 전용 로그인 화면 — 아이디/비밀번호 없이 소셜 계정으로만 로그인
"use client";

import React from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function LoginPage() {
    // 소셜 로그인 핸들러
    const handleSocialLogin = async (provider: 'kakao' | 'naver' | 'google') => {
        try {
            const response = await fetch(`${API_BASE}/api/oauth/${provider}/login`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                // authUrl 또는 redirectUrl이 있으면 이동
                const redirectUrl = data.authUrl || data.redirectUrl;
                if (redirectUrl) {
                    window.location.href = redirectUrl;
                } else {
                    console.log('Login response:', data);
                    alert('로그인 URL을 받지 못했습니다.');
                }
            } else {
                // 에러 응답의 상세 정보 확인
                let errorMessage = `Login failed: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.message || errorData.error || errorMessage;
                } catch (e) {
                    // JSON 파싱 실패 시 텍스트로 읽기 시도
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

    return (
        <div className="min-h-screen bg-background flex items-center justify-center px-4 py-16">
            <div className="w-full max-w-md">
                {/* 브랜드 */}
                <div className="text-center mb-8">
                    <Link href="/" className="inline-flex items-baseline gap-2">
                        <span className="text-xl font-extrabold tracking-tight text-foreground">청년 인사이트</span>
                        <span className="text-xs font-medium text-muted-foreground">Global Pulse</span>
                    </Link>
                </div>

                <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
                    <h1 className="text-2xl font-bold text-center text-foreground mb-2">로그인</h1>
                    <p className="text-center text-sm text-muted-foreground mb-8">
                        SNS 계정으로 간편하게 시작하세요.
                    </p>

                    {/* 소셜 로그인 버튼 */}
                    <div className="space-y-3">
                        {/* Kakao */}
                        <button
                            type="button"
                            onClick={() => handleSocialLogin('kakao')}
                            className="flex w-full items-center justify-center gap-3 rounded-lg bg-[#FEE500] py-3.5 font-medium text-[#191600] transition hover:brightness-95 cursor-pointer"
                        >
                            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <path d="M12 3c5.799 0 10.5 3.664 10.5 8.185 0 4.52-4.701 8.184-10.5 8.184a13.5 13.5 0 0 1-1.727-.11l-4.408 2.883c-.501.265-.678.236-.472-.413l.892-3.678c-2.88-1.46-4.785-3.99-4.785-6.866C1.5 6.665 6.201 3 12 3z" />
                            </svg>
                            카카오로 계속하기
                        </button>

                        {/* Naver */}
                        <button
                            type="button"
                            onClick={() => handleSocialLogin('naver')}
                            className="flex w-full items-center justify-center gap-3 rounded-lg bg-[#03C75A] py-3.5 font-medium text-white transition hover:brightness-95 cursor-pointer"
                        >
                            <span className="text-lg font-extrabold leading-none">N</span>
                            네이버로 계속하기
                        </button>

                        {/* Google */}
                        <button
                            type="button"
                            onClick={() => handleSocialLogin('google')}
                            className="flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-white py-3.5 font-medium text-slate-700 transition hover:bg-slate-50 cursor-pointer"
                        >
                            <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                            </svg>
                            Google로 계속하기
                        </button>
                    </div>
                </div>

                {/* 회원가입 안내 */}
                <p className="mt-6 text-center text-sm text-muted-foreground">
                    아직 회원이 아니신가요?{' '}
                    <Link href="/signup" className="font-semibold text-primary hover:underline">
                        회원가입
                    </Link>
                </p>
            </div>
        </div>
    );
}
