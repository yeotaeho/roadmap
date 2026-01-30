"use client";

import React from 'react';
import { useInView } from 'react-intersection-observer';
import { motion } from 'framer-motion';
import Link from 'next/link';

export interface NewsArticle {
    id: string;
    date: string;
    title: string;
    description?: string;
    link?: string;
}

interface NewsSectionProps {
    news?: NewsArticle[];
}

// 기본 뉴스 데이터
const defaultNews: NewsArticle[] = [
    {
        id: '1',
        date: '2025.12.22',
        title: '[PRESS RELEASE] 오스템바스큘라, 웹어워드 코리아 2025 의료기기 분야 대상 수상',
        description: '혈관 의료기기 전문성과 사용자 편의를 반영한 웹사이트 전면 개편',
    },
    {
        id: '2',
        date: '2025.11.24',
        title: '「오스템바스큘라」 홈페이지 리뉴얼!',
        description: '회사 및 제품에 정보 및 소식을 보다 정확하게 안내해 드리고자 합니다.',
    },
    {
        id: '3',
        date: '2025.07.14',
        title: 'CENTUM Registry 임상 결과 KCJ 게재',
        description: 'CENTUM에 대한 최신 Registry 임상시험 결과가 SICE급 국제 학술 저널인 KCJ에 게재되었습니다.',
    },
    {
        id: '4',
        date: '2025.05.01',
        title: '새로운 PTCA 풍선카테터, BeMotion 시리즈 출시',
        description: '국내에서 직접 제조하는 새로운 PTCA 풍선카테터를 출시하였습니다.',
    },
];

/**
 * 뉴스 섹션 컴포넌트
 */
const NewsSection: React.FC<NewsSectionProps> = ({ news = defaultNews }) => {
    const [ref, inView] = useInView({
        triggerOnce: true,
        threshold: 0.1,
    });

    return (
        <section id="news" className="py-20 lg:py-32 bg-white">
            <div className="container mx-auto px-6 lg:px-10">
                {/* 섹션 헤더 */}
                <motion.div
                    ref={ref}
                    initial={{ opacity: 0, y: 30 }}
                    animate={inView ? { opacity: 1, y: 0 } : {}}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-16"
                >
                    <h2 className="text-4xl lg:text-5xl font-extrabold text-gray-900 mb-4">
                        NEWS
                    </h2>
                    <p className="text-lg text-gray-600">
                        오스템바스큘라의 새로운 소식을 알려드립니다.
                    </p>
                </motion.div>

                {/* 뉴스 목록 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto">
                    {news.map((article, index) => (
                        <motion.article
                            key={article.id}
                            initial={{ opacity: 0, y: 30 }}
                            animate={inView ? { opacity: 1, y: 0 } : {}}
                            transition={{ duration: 0.5, delay: index * 0.1 }}
                            className="border-b border-gray-200 pb-8 hover:border-orange-600 transition-colors"
                        >
                            {article.link ? (
                                <Link href={article.link} className="block group">
                                    <div className="text-sm text-gray-500 mb-2">{article.date}</div>
                                    <h3 className="text-xl font-bold text-gray-900 mb-3 group-hover:text-orange-600 transition-colors">
                                        {article.title}
                                    </h3>
                                    {article.description && (
                                        <p className="text-gray-600 leading-relaxed">
                                            {article.description}
                                        </p>
                                    )}
                                </Link>
                            ) : (
                                <div>
                                    <div className="text-sm text-gray-500 mb-2">{article.date}</div>
                                    <h3 className="text-xl font-bold text-gray-900 mb-3">
                                        {article.title}
                                    </h3>
                                    {article.description && (
                                        <p className="text-gray-600 leading-relaxed">
                                            {article.description}
                                        </p>
                                    )}
                                </div>
                            )}
                        </motion.article>
                    ))}
                </div>

                {/* 더보기 버튼 */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={inView ? { opacity: 1 } : {}}
                    transition={{ duration: 0.6, delay: 0.4 }}
                    className="text-center mt-12"
                >
                    <a
                        href="#news"
                        className="inline-block px-6 py-3 border border-gray-900 rounded-md hover:bg-gray-100 transition duration-150 font-medium"
                    >
                        뉴스 더보기
                    </a>
                </motion.div>
            </div>
        </section>
    );
};

export default NewsSection;

