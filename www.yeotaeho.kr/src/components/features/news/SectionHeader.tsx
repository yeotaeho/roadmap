import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface SectionHeaderProps {
  title: string;
  showPagination?: boolean;
  hasButton?: boolean;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  showPagination = false,
  hasButton = false,
}) => {
  return (
    <div className="flex justify-between items-center mb-6">
      <h2 className="text-xl md:text-2xl font-bold text-gray-800">{title}</h2>
      {showPagination && (
        <div className="flex items-center space-x-2">
          <span className="text-gray-600 text-sm">01 / 06</span>
          <button className="p-2 border border-gray-300 rounded-full hover:bg-gray-100 transition">
            <ChevronLeft size={16} />
          </button>
          <button className="p-2 border border-gray-300 rounded-full hover:bg-gray-100 transition">
            <ChevronRight size={16} />
          </button>
        </div>
      )}
      {hasButton && (
        <button className="hidden sm:flex items-center text-sm font-medium text-white bg-black hover:bg-gray-700 transition px-6 py-3 rounded-full">
          더 많은 이야기 보러가기
        </button>
      )}
    </div>
  );
};

