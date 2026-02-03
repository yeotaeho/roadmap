import React from 'react';

interface Article {
  type: string;
  title: string;
  date?: string;
  image: string;
  link?: string;
}

interface ArticleCardProps {
  article: Article;
  large?: boolean;
}

export const ArticleCard: React.FC<ArticleCardProps> = ({ article, large = false }) => {
  return (
    <a
      href={article.link || '#'}
      target="_blank"
      rel="noopener noreferrer"
      className={`flex flex-col group rounded-lg overflow-hidden hover:shadow-lg transition ${large ? 'col-span-1 sm:col-span-2 md:col-span-1' : 'col-span-1'}`}
    >
      <div className="aspect-[4/2.5] bg-gray-100">
        <img
          src={article.image}
          alt={article.title}
          className="w-full h-full object-cover"
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            target.style.display = 'none';
          }}
        />
      </div>
      <div className="p-4 bg-white flex flex-col flex-grow">
        <span className="text-xs font-semibold text-red-600 uppercase">{article.type || '뉴스'}</span>
        <h3 className={`mt-1 font-bold ${large ? 'text-lg' : 'text-base'} line-clamp-2 group-hover:text-red-600 transition flex-grow`}>
          {article.title}
        </h3>
        {article.date && <p className="mt-2 text-xs text-gray-500">{article.date}</p>}
      </div>
    </a>
  );
};

