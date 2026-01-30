"use client";

import React from 'react';
import { useInView } from 'react-intersection-observer';
import { motion } from 'framer-motion';
import ProductCard, { ProductCardData } from './ProductCard';

// 제품 데이터
const products: ProductCardData[] = [
    {
        id: 'cardiovascular-1',
        title: 'CETNUM™',
        category: 'Cardiovascular',
        description: '오스템바스큘라만의 독자적인 기술력으로 설계한 약물방출관상동맥용스텐트, PTCA 풍선카테터 등 혁신적인 심혈관 의료기기 제품을 공급합니다.',
        link: '#cardiovascular',
    },
    {
        id: 'cardiovascular-2',
        title: 'OPTIMA',
        category: 'Cardiovascular',
        description: '최첨단 기술로 개발된 심혈관 치료 솔루션으로 의료진과 환자에게 최적의 치료 옵션을 제공합니다.',
        link: '#cardiovascular',
    },
    {
        id: 'cardiovascular-3',
        title: 'INJET',
        category: 'Cardiovascular',
        description: '정밀한 설계와 우수한 품질로 신뢰할 수 있는 심혈관 의료기기를 제공합니다.',
        link: '#cardiovascular',
    },
    {
        id: 'neurovascular-1',
        title: 'Neurovascular Products',
        category: 'Neurovascular',
        description: 'Balt Group과의 글로벌 파트너십을 통해 뇌혈관 질환 치료를 위한 세계적인 수준의 의료기기를 소개합니다.',
        link: '#neurovascular',
    },
    {
        id: 'accessories-1',
        title: 'Balloon Expander',
        category: 'Accessories',
        description: '혈관 중재 시술에 필수적인 풍선확장기 등 다양한 의료기기를 개발 및 공급합니다.',
        link: '#accessories',
    },
    {
        id: 'accessories-2',
        title: 'Hemostatic Valve',
        category: 'Accessories',
        description: '안전하고 신뢰할 수 있는 지혈밸브로 시술의 안정성을 보장합니다.',
        link: '#accessories',
    },
];

/**
 * 제품 라인업 섹션 컴포넌트
 */
const ProductLineup: React.FC = () => {
    const [ref, inView] = useInView({
        triggerOnce: true,
        threshold: 0.1,
    });

    return (
        <section id="products" className="py-20 lg:py-32 bg-white">
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
                        PRODUCT LINE UP
                    </h2>
                    <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                        오스템바스큘라만의 독자적인 기술력으로 설계한 혁신적인 의료기기 제품을 소개합니다.
                    </p>
                </motion.div>

                {/* 제품 그리드 */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    {products.map((product, index) => (
                        <ProductCard key={product.id} product={product} index={index} />
                    ))}
                </div>
            </div>
        </section>
    );
};

export default ProductLineup;

