import React from 'react';
import { ArticleCard } from './ArticleCard';

interface NewsArticle {
  type: string;
  title: string;
  date?: string;
  image: string;
  link?: string;
  description?: string;
}

interface NewsListProps {
  articles: NewsArticle[];
  loading?: boolean;
  activeTab?: string;
}

export const NewsList: React.FC<NewsListProps> = ({ articles, loading = false, activeTab = '전체 기사' }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(8)].map((_, index) => (
          <div key={index} className="flex flex-col rounded-lg overflow-hidden animate-pulse">
            <div className="aspect-[4/2.5] bg-gray-200"></div>
            <div className="p-4 bg-white">
              <div className="h-4 bg-gray-200 rounded w-20 mb-2"></div>
              <div className="h-5 bg-gray-200 rounded w-full mb-2"></div>
              <div className="h-3 bg-gray-200 rounded w-24"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg mb-2">
          {activeTab === '전체 기사'
            ? '뉴스를 불러올 수 없습니다.'
            : `'${activeTab}' 카테고리의 뉴스가 없습니다.`}
        </p>
        <p className="text-gray-400 text-sm">
          다른 카테고리를 선택하거나 잠시 후 다시 시도해주세요.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      {articles.map((article, index) => (
        <ArticleCard
          key={`${article.title}-${index}`}
          article={article}
        />
      ))}
    </div>
  );
};

