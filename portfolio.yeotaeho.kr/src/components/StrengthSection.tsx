"use client";

import React from 'react';
import { useInView } from 'react-intersection-observer';
import { motion } from 'framer-motion';

/**
 * 회사 강점 섹션 컴포넌트
 */
const StrengthSection: React.FC = () => {
    const [ref, inView] = useInView({
        triggerOnce: true,
        threshold: 0.1,
    });

    const strengths = [
        {
            title: 'Since 1994',
            subtitle: '개발부터 제조까지',
            description: '모든 것을 스스로 이뤄내다',
        },
        {
            title: 'MISSION',
            subtitle: '삶의 질 향상에 기여하는',
            description: '혈관 의료기기 전문기업',
        },
        {
            title: 'VISION',
            subtitle: '혈관 질환 치료에 필요한 토탈 솔루션을',
            description: '제공하여 보다 나은 미래 가치 창출',
        },
    ];

    return (
        <section id="company" className="py-20 lg:py-32 bg-gray-50">
            <div className="container mx-auto px-6 lg:px-10">
                <motion.div
                    ref={ref}
                    initial={{ opacity: 0, y: 30 }}
                    animate={inView ? { opacity: 1, y: 0 } : {}}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-16"
                >
                    <h2 className="text-4xl lg:text-5xl font-extrabold text-gray-900 mb-4">
                        STRENGTH
                    </h2>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
                    {strengths.map((strength, index) => (
                        <motion.div
                            key={strength.title}
                            initial={{ opacity: 0, y: 30 }}
                            animate={inView ? { opacity: 1, y: 0 } : {}}
                            transition={{ duration: 0.6, delay: index * 0.2 }}
                            className="text-center"
                        >
                            <h3 className="text-2xl lg:text-3xl font-bold text-orange-600 mb-4">
                                {strength.title}
                            </h3>
                            <p className="text-lg font-semibold text-gray-900 mb-2">
                                {strength.subtitle}
                            </p>
                            <p className="text-gray-600">
                                {strength.description}
                            </p>
                        </motion.div>
                    ))}
                </div>

                {/* 추가 설명 */}
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    animate={inView ? { opacity: 1, y: 0 } : {}}
                    transition={{ duration: 0.6, delay: 0.6 }}
                    className="mt-16 text-center"
                >
                    <h3 className="text-2xl lg:text-3xl font-extrabold text-gray-900 mb-6">
                        INNOVATIVE VASCULAR SOLUTIONS THAT GO BEYOND
                    </h3>
                    <p className="text-lg text-gray-600 max-w-3xl mx-auto leading-relaxed">
                        지속적 연구개발과 제조 노하우, 철저한 품질관리를 통해 신뢰할 수 있는 제품과 솔루션을 제공하며
                        혈관 질환 치료의 새로운 길을 열어가고자 합니다.
                    </p>
                </motion.div>
            </div>
        </section>
    );
};

export default StrengthSection;

