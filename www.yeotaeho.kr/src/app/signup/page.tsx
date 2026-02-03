"use client";

import React, { useState } from 'react';

export default function SignupPage() {
    // 나이와 관심분야 상태 관리
    const [age, setAge] = useState<number | ''>('');
    const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
    const [customInterest, setCustomInterest] = useState<string>('');

    // 관심분야 옵션
    const interestOptions = [
        { value: 'economy', label: '경제' },
        { value: 'politics', label: '정치' },
        { value: 'society', label: '사회' },
        { value: 'culture', label: '문화' },
        { value: 'world', label: '세계' },
        { value: 'it-science', label: 'IT/과학' },
        { value: 'sports', label: '스포츠' },
        { value: 'entertainment', label: '연예' },
    ];

    // 관심분야 선택 핸들러
    const handleInterestToggle = (value: string) => {
        setSelectedInterests(prev =>
            prev.includes(value)
                ? prev.filter(item => item !== value)
                : [...prev, value]
        );
    };

    // 커스텀 관심분야 추가 핸들러
    const handleAddCustomInterest = () => {
        if (customInterest.trim() && !selectedInterests.includes(customInterest.trim())) {
            setSelectedInterests(prev => [...prev, customInterest.trim()]);
            setCustomInterest('');
        }
    };

    // 커스텀 관심분야 제거 핸들러
    const handleRemoveInterest = (value: string) => {
        setSelectedInterests(prev => prev.filter(item => item !== value));
    };

    // 소셜 로그인 핸들러 (회원가입 모드)
    const handleSocialLogin = async (provider: 'kakao' | 'naver' | 'google') => {
        // 필수 입력 검증
        if (!age || age < 1 || age > 120) {
            alert('나이를 입력해주세요. (1-120)');
            return;
        }

        if (selectedInterests.length === 0) {
            alert('최소 1개 이상의 관심분야를 선택해주세요.');
            return;
        }

        // 입력한 정보를 localStorage에 저장 (콜백에서 사용하기 위해)
        localStorage.setItem('signup_age', age.toString());
        localStorage.setItem('signup_interests', JSON.stringify(selectedInterests));
        try {
            const response = await fetch(`http://localhost:8000/api/oauth/${provider}/login?mode=signup`, {
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

                {/* 나이 입력 */}
                <div className="mb-6">
                    <label htmlFor="age" className="block text-sm font-medium text-gray-700 mb-2">
                        나이 <span className="text-red-500">*</span>
                    </label>
                    <input
                        id="age"
                        type="number"
                        min="1"
                        max="120"
                        value={age}
                        onChange={(e) => setAge(e.target.value === '' ? '' : parseInt(e.target.value))}
                        placeholder="나이를 입력하세요"
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                    />
                </div>

                {/* 관심분야 선택 */}
                <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-700 mb-3">
                        관심분야 (복수 선택 가능) <span className="text-red-500">*</span>
                    </label>
                    <div className="grid grid-cols-2 gap-3 mb-4">
                        {interestOptions.map((option) => (
                            <label
                                key={option.value}
                                className={`flex items-center p-3 border-2 rounded-lg cursor-pointer transition ${selectedInterests.includes(option.value)
                                    ? 'border-black bg-black text-white'
                                    : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                                    }`}
                            >
                                <input
                                    type="checkbox"
                                    checked={selectedInterests.includes(option.value)}
                                    onChange={() => handleInterestToggle(option.value)}
                                    className="sr-only"
                                />
                                <span className="text-sm font-medium">{option.label}</span>
                            </label>
                        ))}
                    </div>

                    {/* 커스텀 관심분야 입력 */}
                    <div className="flex gap-2 mb-3">
                        <input
                            type="text"
                            value={customInterest}
                            onChange={(e) => setCustomInterest(e.target.value)}
                            onKeyPress={(e) => {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    handleAddCustomInterest();
                                }
                            }}
                            placeholder="직접 입력하세요"
                            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                        />
                        <button
                            type="button"
                            onClick={handleAddCustomInterest}
                            disabled={!customInterest.trim()}
                            className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-black transition disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            추가
                        </button>
                    </div>

                    {/* 선택된 관심분야 표시 */}
                    {selectedInterests.length > 0 && (
                        <div className="mt-3">
                            <p className="text-xs text-gray-500 mb-2">선택된 관심분야:</p>
                            <div className="flex flex-wrap gap-2">
                                {selectedInterests.map((interest) => {
                                    const option = interestOptions.find(opt => opt.value === interest);
                                    return (
                                        <span
                                            key={interest}
                                            className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                                        >
                                            {option ? option.label : interest}
                                            <button
                                                type="button"
                                                onClick={() => handleRemoveInterest(interest)}
                                                className="ml-1 text-gray-500 hover:text-black"
                                            >
                                                ×
                                            </button>
                                        </span>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>

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
