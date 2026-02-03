"use client";

import React from 'react';
import { NewsList } from './NewsList';

interface NewsArticle {
  type: string;
  title: string;
  date?: string;
  image: string;
  link?: string;
  description?: string;
}

interface RecentArticlesProps {
  activeTab: string;
  recentArticles: NewsArticle[];
  loading: boolean;
  onTabChange: (tab: string) => void;
}

const HEADER_LINKS = ['전체 기사', '경제', '정치', '사회', '문화', '국제/세계', 'IT/과학', '스포츠', '연예'];

export const RecentArticles: React.FC<RecentArticlesProps> = ({
  activeTab,
  recentArticles,
  loading,
  onTabChange,
}) => {
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-16">
      <h2 className="text-2xl font-bold mb-6 border-b pb-2">최신 기사</h2>

      {/* Tabs */}
      <div className="flex overflow-x-auto space-x-4 pb-2 border-b border-gray-200 mb-8 whitespace-nowrap">
        {HEADER_LINKS.map(link => (
          <button
            key={link}
            onClick={() => onTabChange(link)}
            disabled={loading}
            className={`py-2 px-3 text-sm font-medium transition duration-300 ease-in-out relative ${
              activeTab === link
                ? 'text-black border-b-2 border-red-600'
                : 'text-gray-500 hover:text-red-600'
            } ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            {link}
            {loading && activeTab === link && (
              <span className="absolute -bottom-1 left-1/2 transform -translate-x-1/2">
                <span className="flex space-x-1">
                  <span className="w-1 h-1 bg-red-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-1 h-1 bg-red-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-1 h-1 bg-red-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </span>
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Category Info */}
      {!loading && recentArticles.length > 0 && (
        <div className="flex justify-between items-center mb-4">
          <p className="text-sm text-gray-600">
            <span className="font-semibold text-red-600">{activeTab}</span> 카테고리 • 총 {recentArticles.length}개의 기사
          </p>
          <button className="text-xs text-gray-500 hover:text-red-600 transition">
            최신순 ▼
          </button>
        </div>
      )}

      {/* Articles Grid */}
      <NewsList articles={recentArticles} loading={loading} activeTab={activeTab} />
    </section>
  );
};

