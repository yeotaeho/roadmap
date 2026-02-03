"use client";

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Search, AlignJustify } from 'lucide-react';
import { useAuth } from '@/hooks/useStore';

const NAV_LINKS = ['트랜드 분석', '챗', '프레스센터', '뉴스룸소개'];

interface HeaderProps {
  userName?: string | null;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ userName, onLogout }) => {
  const router = useRouter();
  const { isAuthenticated, logoutAsync } = useAuth();

  const handleLogout = async () => {
    try {
      await logoutAsync();
      if (onLogout) {
        onLogout();
      }
      router.push('/');
      router.refresh();
    } catch (error) {
      console.error('로그아웃 처리 중 오류:', error);
    }
  };

  return (
    <header className="sticky top-0 z-50 bg-white shadow-md border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
        {/* Logo */}
        <div className="flex items-center space-x-12">
          <div className="text-xl font-extrabold text-gray-800">
            SAMSUNG <span className="font-normal text-sm block -mt-1">Newsroom</span>
          </div>
          {/* Desktop Navigation */}
          <nav className="hidden lg:flex space-x-6 text-sm">
            {NAV_LINKS.map(link => (
              <Link
                key={link}
                href={link === '트랜드 분석' ? '/trend-analysis' : link === '챗' ? '/chat' : '#'}
                className="text-gray-600 hover:text-red-600 transition font-medium"
              >
                {link}
              </Link>
            ))}
          </nav>
        </div>
        {/* Login & Signup Buttons, Icons & Mobile Menu */}
        <div className="flex items-center space-x-4">
          {/* 로그인 상태에 따라 다른 UI 표시 */}
          {isAuthenticated ? (
            <div className="hidden lg:flex items-center space-x-3">
              <Link
                href="/profile"
                className="px-4 py-2 text-sm text-gray-700 font-medium hover:text-red-600 transition cursor-pointer"
              >
                {userName || '사용자'}님
              </Link>
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 transition font-medium rounded-full"
              >
                로그아웃
              </button>
            </div>
          ) : (
            <div className="hidden lg:flex items-center space-x-3">
              <Link href="/login" className="px-4 py-2 text-sm text-gray-700 hover:text-red-600 transition font-medium">
                로그인
              </Link>
              <Link href="/signup" className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 transition font-medium rounded-full">
                회원가입
              </Link>
            </div>
          )}
          <button className="p-2 text-gray-600 hover:text-red-600 transition">
            <Search size={20} />
          </button>
          <button className="lg:hidden p-2 text-gray-600 hover:text-red-600 transition">
            <AlignJustify size={20} />
          </button>
        </div>
      </div>
    </header>
  );
};

