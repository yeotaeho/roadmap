"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
    const [showPassword, setShowPassword] = useState(false);
    const [saveId, setSaveId] = useState(false);

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
        <div className="min-h-screen bg-white flex items-center justify-center px-4 py-24">
            <div className="w-full max-w-3xl">
                {/* LOGIN Header */}
                <h1 className="text-4xl font-bold text-black text-center mb-12">LOGIN</h1>

                {/* Input Fields */}
                <div className="space-y-6 mb-10">
                    {/* ID Input */}
                    <input
                        type="text"
                        placeholder="아이디를 입력해 주세요"
                        className="w-full px-4 py-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent text-gray-700 placeholder-gray-400"
                    />

                    {/* Password Input */}
                    <div className="relative">
                        <input
                            type={showPassword ? "text" : "password"}
                            placeholder="비밀번호를 입력해 주세요"
                            className="w-full px-4 py-4 pr-12 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent text-gray-700 placeholder-gray-400"
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                        >
                            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                        </button>
                    </div>
                </div>

                {/* Login Options */}
                <div className="flex justify-between items-center mb-10">
                    {/* Save ID Checkbox */}
                    <label className="flex items-center cursor-pointer">
                        <input
                            type="checkbox"
                            checked={saveId}
                            onChange={(e) => setSaveId(e.target.checked)}
                            className="w-4 h-4 border-gray-300 rounded text-black focus:ring-black"
                        />
                        <span className="ml-2 text-sm text-gray-600">아이디 저장</span>
                    </label>

                    {/* Find ID & Password Links */}
                    <div className="flex items-center space-x-2 text-sm">
                        <a href="#" className="text-gray-600 hover:text-black transition">아이디 찾기</a>
                        <span className="text-gray-300">|</span>
                        <a href="#" className="text-gray-600 hover:text-black transition">비밀번호 찾기</a>
                    </div>
                </div>

                {/* Login Button */}
                <button className="w-full bg-black text-white py-4 rounded-md font-medium hover:bg-gray-800 transition mb-10 text-lg">
                    로그인
                </button>

                {/* Social Login */}
                <div className="flex justify-center items-center space-x-4 mb-10">
                    {/* Kakao */}
                    <button 
                        onClick={() => handleSocialLogin('kakao')}
                        className="w-16 h-16 bg-yellow-400 rounded-full flex items-center justify-center hover:bg-yellow-500 transition cursor-pointer"
                    >
                        <svg className="w-8 h-8 text-black" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 3c5.799 0 10.5 3.664 10.5 8.185 0 4.52-4.701 8.184-10.5 8.184a13.5 13.5 0 0 1-1.727-.11l-4.408 2.883c-.501.265-.678.236-.472-.413l.892-3.678c-2.88-1.46-4.785-3.99-4.785-6.866C1.5 6.665 6.201 3 12 3z"/>
                        </svg>
                    </button>

                    {/* Naver */}
                    <button 
                        onClick={() => handleSocialLogin('naver')}
                        className="w-16 h-16 bg-green-500 rounded-full flex items-center justify-center hover:bg-green-600 transition cursor-pointer"
                    >
                        <span className="text-white font-bold text-xl">N</span>
                    </button>

                    {/* Google */}
                    <button 
                        onClick={() => handleSocialLogin('google')}
                        className="w-16 h-16 bg-white border border-gray-300 rounded-full flex items-center justify-center hover:bg-gray-50 transition shadow-sm cursor-pointer"
                    >
                        <svg className="w-8 h-8" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                        </svg>
                    </button>
                </div>

                {/* Divider */}
                <div className="border-t border-gray-300 mb-10"></div>

                {/* Sign Up Section */}
                <div className="text-center mb-6">
                    <p className="text-black text-sm">회원이 아니신가요?</p>
                </div>

                {/* Sign Up Button */}
                <Link href="/signup" className="block w-full border-2 border-black text-black py-4 rounded-md font-medium text-center hover:bg-gray-50 transition text-lg">
                    회원가입
                </Link>
            </div>
        </div>
    );
}

