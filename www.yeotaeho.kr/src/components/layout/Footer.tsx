import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-gray-100 mt-12 py-8 border-t border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center space-y-4 md:space-y-0">
          <div className="text-lg font-extrabold text-gray-800">
            SAMSUNG
          </div>
          <div className="flex space-x-4 text-sm text-gray-600">
            <a href="#" className="hover:text-red-600">이용약관</a>
            <a href="#" className="hover:text-red-600 font-bold">개인정보처리방침</a>
            <a href="#" className="hover:text-red-600">접근성</a>
          </div>
        </div>
        <div className="mt-4 text-xs text-gray-500">
          <p>Copyright © 2025 Samsung. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
};

