"use client";

import React from 'react';
import Header from '@/components/Header';
import HeroSection from '@/components/HeroSection';
import ProductLineup from '@/components/ProductLineup';
import StrengthSection from '@/components/StrengthSection';
import NewsSection from '@/components/NewsSection';

/**
 * 메인 페이지 컴포넌트
 */
const HomePage: React.FC = () => {
    return (
        <div className="min-h-screen antialiased">
            <Header />
            <main>
                <HeroSection />
                <ProductLineup />
                <StrengthSection />
                <NewsSection />
            </main>
        </div>
    );
};

export default HomePage;

