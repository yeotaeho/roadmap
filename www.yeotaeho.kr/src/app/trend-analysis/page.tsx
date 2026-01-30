"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { TrendingUp, TrendingDown, BarChart3, PieChart, Globe, Calendar, ArrowRight, Search, Loader2, ChevronDown } from 'lucide-react';
import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion';
import { useInView } from 'react-intersection-observer';

// 트랜드 데이터 타입
interface TrendData {
    category: string;
    trend: 'up' | 'down' | 'stable';
    value: number;
    change: number;
    prediction: string;
    description: string;
}

// 예측 데이터 타입
interface PredictionData {
    title: string;
    category: string;
    currentValue: number;
    predictedValue: number;
    confidence: number;
    timeframe: string;
    factors: string[];
}

// Mock 데이터
const trendCategories: TrendData[] = [
    {
        category: '기술/IT',
        trend: 'up',
        value: 85,
        change: 12.5,
        prediction: 'AI와 머신러닝 기술이 지속적으로 성장할 것으로 예측됩니다.',
        description: '인공지능, 클라우드 컴퓨팅, 사이버 보안 분야가 급성장 중입니다.'
    },
    {
        category: '경제/금융',
        trend: 'up',
        value: 72,
        change: 8.3,
        prediction: '디지털 금융과 블록체인 기술이 금융 산업을 혁신할 것입니다.',
        description: '핀테크와 암호화폐 시장이 안정적인 성장세를 보이고 있습니다.'
    },
    {
        category: '환경/에너지',
        trend: 'up',
        value: 68,
        change: 15.2,
        prediction: '재생 에너지와 친환경 기술에 대한 관심이 급증할 것입니다.',
        description: '탄소 중립 정책과 ESG 경영이 주요 트렌드로 부상했습니다.'
    },
    {
        category: '의료/바이오',
        trend: 'up',
        value: 65,
        change: 9.7,
        prediction: '개인 맞춤형 의료와 디지털 헬스케어가 확산될 것입니다.',
        description: '원격 진료와 AI 진단 기술이 의료 산업을 변화시키고 있습니다.'
    },
    {
        category: '교육',
        trend: 'stable',
        value: 55,
        change: 2.1,
        prediction: '온라인 교육과 평생 학습이 새로운 표준이 될 것입니다.',
        description: '에듀테크와 스킬 기반 교육이 주목받고 있습니다.'
    },
    {
        category: '소비자 트렌드',
        trend: 'down',
        value: 45,
        change: -5.3,
        prediction: '지속 가능한 소비와 공유 경제가 확대될 것입니다.',
        description: '밀레니얼과 Z세대의 소비 패턴 변화가 두드러집니다.'
    }
];

const predictions: PredictionData[] = [
    {
        title: 'AI 기술 확산',
        category: '기술/IT',
        currentValue: 65,
        predictedValue: 85,
        confidence: 92,
        timeframe: '6개월',
        factors: ['대규모 언어 모델 발전', '기업의 AI 도입 가속', '정부 정책 지원']
    },
    {
        title: '친환경 에너지 전환',
        category: '환경/에너지',
        currentValue: 50,
        predictedValue: 75,
        confidence: 88,
        timeframe: '1년',
        factors: ['재생 에너지 기술 발전', '탄소 규제 강화', '기업 ESG 경영 확대']
    },
    {
        title: '원격 근무 정착',
        category: '사회/문화',
        currentValue: 40,
        predictedValue: 60,
        confidence: 85,
        timeframe: '9개월',
        factors: ['디지털 인프라 구축', '근무 문화 변화', '생산성 도구 발전']
    },
    {
        title: '개인화 서비스',
        category: '소비자 트렌드',
        currentValue: 55,
        predictedValue: 70,
        confidence: 90,
        timeframe: '1년',
        factors: ['빅데이터 분석 기술', 'AI 추천 시스템', '고객 경험 중시']
    }
];

// 트렌드 카드 컴포넌트
const TrendCard = ({ trend, index, getTrendIcon, getTrendColor }: {
    trend: TrendData;
    index: number;
    getTrendIcon: (trend: string) => React.ReactElement;
    getTrendColor: (trend: string) => string;
}) => {
    const [ref, inView] = useInView({
        triggerOnce: true,
        threshold: 0.1,
    });

    const [animatedValue, setAnimatedValue] = useState(0);

    useEffect(() => {
        if (inView) {
            const duration = 1500;
            const steps = 60;
            const increment = trend.value / steps;
            let current = 0;
            const timer = setInterval(() => {
                current += increment;
                if (current >= trend.value) {
                    setAnimatedValue(trend.value);
                    clearInterval(timer);
                } else {
                    setAnimatedValue(current);
                }
            }, duration / steps);
            return () => clearInterval(timer);
        }
    }, [inView, trend.value]);

    return (
        <motion.div
            ref={ref}
            initial={{ opacity: 0, y: 50 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{
                duration: 0.5,
                delay: index * 0.1,
                layout: { duration: 0.08, ease: "easeOut" },
                default: { duration: 0.08, ease: "easeOut" }
            }}
            whileHover={{
                y: -5,
                scale: 1.02,
                transition: { duration: 0.2, ease: "easeOut" }
            }}
            className="bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow duration-100 p-6 border border-gray-200"
        >
            <div className="flex items-center justify-between mb-4">
                <motion.h3
                    className="text-xl font-bold text-gray-900"
                    initial={{ opacity: 0, x: -20 }}
                    animate={inView ? { opacity: 1, x: 0 } : {}}
                    transition={{ delay: index * 0.1 + 0.2 }}
                >
                    {trend.category}
                </motion.h3>
                <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={inView ? { scale: 1, rotate: 0 } : {}}
                    transition={{ delay: index * 0.1 + 0.3, type: "spring" }}
                >
                    {getTrendIcon(trend.trend)}
                </motion.div>
            </div>

            <div className="mb-4">
                <div className="flex items-baseline space-x-2 mb-2">
                    <motion.span
                        className="text-3xl font-extrabold text-gray-900"
                        initial={{ opacity: 0 }}
                        animate={inView ? { opacity: 1 } : {}}
                        transition={{ delay: index * 0.1 + 0.4 }}
                    >
                        {Math.round(animatedValue)}
                    </motion.span>
                    <span className="text-sm text-gray-500">/ 100</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                    <motion.div
                        className={`h-3 rounded-full ${trend.trend === 'up' ? 'bg-green-500' :
                            trend.trend === 'down' ? 'bg-red-500' : 'bg-gray-500'
                            }`}
                        initial={{ width: 0 }}
                        animate={inView ? { width: `${trend.value}%` } : {}}
                        transition={{ duration: 1.5, delay: index * 0.1 + 0.5, ease: "easeOut" }}
                    />
                </div>
            </div>

            <motion.div
                className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium mb-4 ${getTrendColor(trend.trend)}`}
                initial={{ opacity: 0, scale: 0 }}
                animate={inView ? { opacity: 1, scale: 1 } : {}}
                transition={{ delay: index * 0.1 + 0.6, type: "spring" }}
            >
                {trend.change > 0 ? '+' : ''}{trend.change}%
            </motion.div>

            <motion.p
                className="text-gray-600 text-sm mb-4"
                initial={{ opacity: 0 }}
                animate={inView ? { opacity: 1 } : {}}
                transition={{ delay: index * 0.1 + 0.7 }}
            >
                {trend.description}
            </motion.p>
            <motion.div
                className="bg-blue-50 border-l-4 border-blue-500 p-3 rounded"
                initial={{ opacity: 0, x: -20 }}
                animate={inView ? { opacity: 1, x: 0 } : {}}
                transition={{ delay: index * 0.1 + 0.8 }}
            >
                <p className="text-sm text-blue-900 font-medium">예측: {trend.prediction}</p>
            </motion.div>
        </motion.div>
    );
};

// 트렌드 카드 섹션
const TrendCardsSection = ({ trends, getTrendIcon, getTrendColor }: {
    trends: TrendData[];
    getTrendIcon: (trend: string) => React.ReactElement;
    getTrendColor: (trend: string) => string;
}) => {
    const [ref, inView] = useInView({
        triggerOnce: true,
        threshold: 0.1,
    });

    return (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <motion.div
                ref={ref}
                initial={{ opacity: 0, y: 30 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.6 }}
                className="mb-8"
            >
                <h2 className="text-3xl font-bold text-gray-900 mb-2">현재 트렌드 분석</h2>
                <p className="text-gray-600">주요 카테고리별 트렌드 지표와 변화율을 확인하세요.</p>
            </motion.div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {trends.map((trend, index) => (
                    <TrendCard
                        key={index}
                        trend={trend}
                        index={index}
                        getTrendIcon={getTrendIcon}
                        getTrendColor={getTrendColor}
                    />
                ))}
            </div>
        </section>
    );
};

// 예측 카드 컴포넌트
const PredictionCard = ({ prediction, index }: { prediction: PredictionData; index: number }) => {
    const [ref, inView] = useInView({
        triggerOnce: true,
        threshold: 0.1,
    });

    const [currentAnimated, setCurrentAnimated] = useState(0);
    const [predictedAnimated, setPredictedAnimated] = useState(0);
    const [confidenceAnimated, setConfidenceAnimated] = useState(0);

    useEffect(() => {
        if (inView) {
            const duration = 2000;
            const steps = 60;

            const currentIncrement = prediction.currentValue / steps;
            const predictedIncrement = prediction.predictedValue / steps;
            const confidenceIncrement = prediction.confidence / steps;

            let current = 0;
            let predicted = 0;
            let confidence = 0;

            const timer = setInterval(() => {
                current += currentIncrement;
                predicted += predictedIncrement;
                confidence += confidenceIncrement;

                if (current >= prediction.currentValue) {
                    setCurrentAnimated(prediction.currentValue);
                    setPredictedAnimated(prediction.predictedValue);
                    setConfidenceAnimated(prediction.confidence);
                    clearInterval(timer);
                } else {
                    setCurrentAnimated(current);
                    setPredictedAnimated(predicted);
                    setConfidenceAnimated(confidence);
                }
            }, duration / steps);

            return () => clearInterval(timer);
        }
    }, [inView, prediction]);

    return (
        <motion.div
            ref={ref}
            initial={{ opacity: 0, x: index % 2 === 0 ? -50 : 50 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{
                duration: 0.6,
                delay: index * 0.2,
                layout: { duration: 0.08, ease: "easeOut" },
                default: { duration: 0.08, ease: "easeOut" }
            }}
            whileHover={{
                y: -8,
                scale: 1.02,
                transition: { duration: 0.2, ease: "easeOut" }
            }}
            className="bg-gradient-to-br from-gray-50 to-white rounded-lg shadow-lg hover:shadow-xl transition-shadow duration-100 p-6 border border-gray-200"
        >
            <div className="flex items-start justify-between mb-4">
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={inView ? { opacity: 1, y: 0 } : {}}
                    transition={{ delay: index * 0.2 + 0.2 }}
                >
                    <h3 className="text-2xl font-bold text-gray-900 mb-1">{prediction.title}</h3>
                    <span className="inline-block px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">
                        {prediction.category}
                    </span>
                </motion.div>
                <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={inView ? { scale: 1, rotate: 0 } : {}}
                    transition={{ delay: index * 0.2 + 0.3, type: "spring" }}
                >
                    <PieChart className="w-8 h-8 text-red-600" />
                </motion.div>
            </div>

            <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">현재</span>
                    <span className="text-sm text-gray-600">예측</span>
                </div>
                <div className="flex items-center space-x-4">
                    <div className="flex-1">
                        <motion.div
                            className="text-2xl font-bold text-gray-700"
                            initial={{ opacity: 0 }}
                            animate={inView ? { opacity: 1 } : {}}
                        >
                            {Math.round(currentAnimated)}
                        </motion.div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-1 overflow-hidden">
                            <motion.div
                                className="bg-gray-500 h-2 rounded-full"
                                initial={{ width: 0 }}
                                animate={inView ? { width: `${prediction.currentValue}%` } : {}}
                                transition={{ duration: 1.5, delay: index * 0.2 + 0.4 }}
                            />
                        </div>
                    </div>
                    <motion.div
                        animate={inView ? { x: [0, 10, 0] } : {}}
                        transition={{ duration: 1, repeat: Infinity, delay: index * 0.2 + 0.5 }}
                    >
                        <ArrowRight className="w-5 h-5 text-gray-400" />
                    </motion.div>
                    <div className="flex-1">
                        <motion.div
                            className="text-2xl font-bold text-red-600"
                            initial={{ opacity: 0 }}
                            animate={inView ? { opacity: 1 } : {}}
                        >
                            {Math.round(predictedAnimated)}
                        </motion.div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-1 overflow-hidden">
                            <motion.div
                                className="bg-red-600 h-2 rounded-full"
                                initial={{ width: 0 }}
                                animate={inView ? { width: `${prediction.predictedValue}%` } : {}}
                                transition={{ duration: 1.5, delay: index * 0.2 + 0.6 }}
                            />
                        </div>
                    </div>
                </div>
            </div>

            <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">예측 신뢰도</span>
                    <motion.span
                        className="text-sm font-bold text-gray-900"
                        initial={{ opacity: 0 }}
                        animate={inView ? { opacity: 1 } : {}}
                    >
                        {Math.round(confidenceAnimated)}%
                    </motion.span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                    <motion.div
                        className="bg-green-500 h-2 rounded-full"
                        initial={{ width: 0 }}
                        animate={inView ? { width: `${prediction.confidence}%` } : {}}
                        transition={{ duration: 1.5, delay: index * 0.2 + 0.7 }}
                    />
                </div>
            </div>

            <motion.div
                className="mb-4"
                initial={{ opacity: 0 }}
                animate={inView ? { opacity: 1 } : {}}
                transition={{ delay: index * 0.2 + 0.8 }}
            >
                <span className="text-sm text-gray-600">예측 기간: </span>
                <span className="text-sm font-medium text-gray-900">{prediction.timeframe}</span>
            </motion.div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: index * 0.2 + 0.9 }}
            >
                <p className="text-sm font-medium text-gray-700 mb-2">주요 요인:</p>
                <ul className="space-y-1">
                    {prediction.factors.map((factor, idx) => (
                        <motion.li
                            key={idx}
                            className="text-sm text-gray-600 flex items-center"
                            initial={{ opacity: 0, x: -20 }}
                            animate={inView ? { opacity: 1, x: 0 } : {}}
                            transition={{ delay: index * 0.2 + 1 + idx * 0.1 }}
                        >
                            <motion.span
                                className="w-1.5 h-1.5 bg-red-500 rounded-full mr-2"
                                animate={inView ? { scale: [1, 1.5, 1] } : {}}
                                transition={{ delay: index * 0.2 + 1 + idx * 0.1, duration: 0.5 }}
                            />
                            {factor}
                        </motion.li>
                    ))}
                </ul>
            </motion.div>
        </motion.div>
    );
};

// 예측 섹션
const PredictionsSection = ({ predictions }: { predictions: PredictionData[] }) => {
    const [ref, inView] = useInView({
        triggerOnce: true,
        threshold: 0.1,
    });

    return (
        <section className="bg-white py-12">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <motion.div
                    ref={ref}
                    initial={{ opacity: 0, y: 30 }}
                    animate={inView ? { opacity: 1, y: 0 } : {}}
                    transition={{ duration: 0.6 }}
                    className="mb-8"
                >
                    <h2 className="text-3xl font-bold text-gray-900 mb-2">미래 예측 분석</h2>
                    <p className="text-gray-600">AI 기반 분석을 통한 미래 트렌드 예측입니다.</p>
                </motion.div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {predictions.map((prediction, index) => (
                        <PredictionCard key={index} prediction={prediction} index={index} />
                    ))}
                </div>
            </div>
        </section>
    );
};

export default function TrendAnalysisPage() {
    const [selectedCategory, setSelectedCategory] = useState<string>('전체');
    const [searchQuery, setSearchQuery] = useState('');
    const [isAnalyzing, setIsAnalyzing] = useState(true);
    const [scrollY, setScrollY] = useState(0);
    const { scrollYProgress } = useScroll();

    const categories = ['전체', ...new Set(trendCategories.map(t => t.category))];

    // 분석 중일 때 스크롤 방지 및 스크롤 기반 전환
    useEffect(() => {
        if (isAnalyzing) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }

        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [isAnalyzing]);

    // 스크롤/휠 이벤트로 전환 감지
    useEffect(() => {
        if (!isAnalyzing) return;

        let scrollAccumulator = 0;
        const SCROLL_THRESHOLD = 50; // 스크롤 누적 거리 임계값

        const handleWheel = (e: WheelEvent) => {
            // 스크롤 시도 감지
            scrollAccumulator += Math.abs(e.deltaY);

            if (scrollAccumulator >= SCROLL_THRESHOLD) {
                setIsAnalyzing(false);
                scrollAccumulator = 0;
            }
        };

        // 터치 스크롤 감지 (모바일)
        let touchStartY = 0;
        const handleTouchStart = (e: TouchEvent) => {
            touchStartY = e.touches[0].clientY;
        };

        const handleTouchMove = (e: TouchEvent) => {
            if (!touchStartY) return;
            const touchY = e.touches[0].clientY;
            const deltaY = Math.abs(touchY - touchStartY);

            if (deltaY >= SCROLL_THRESHOLD) {
                setIsAnalyzing(false);
                touchStartY = 0;
            }
        };

        // 키보드 스크롤 감지 (스페이스바, 화살표 키 등)
        const handleKeyDown = (e: KeyboardEvent) => {
            if (['Space', 'ArrowDown', 'PageDown'].includes(e.code)) {
                e.preventDefault();
                setIsAnalyzing(false);
            }
        };

        window.addEventListener('wheel', handleWheel, { passive: true });
        window.addEventListener('touchstart', handleTouchStart, { passive: true });
        window.addEventListener('touchmove', handleTouchMove, { passive: true });
        window.addEventListener('keydown', handleKeyDown);

        return () => {
            window.removeEventListener('wheel', handleWheel);
            window.removeEventListener('touchstart', handleTouchStart);
            window.removeEventListener('touchmove', handleTouchMove);
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, [isAnalyzing]);

    // 일반 스크롤 이벤트 (분석 완료 후)
    useEffect(() => {
        if (isAnalyzing) return;

        const handleScroll = () => {
            setScrollY(window.scrollY);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, [isAnalyzing]);

    const filteredTrends = trendCategories.filter(trend => {
        const matchesCategory = selectedCategory === '전체' || trend.category === selectedCategory;
        const matchesSearch = searchQuery === '' ||
            trend.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
            trend.description.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesCategory && matchesSearch;
    });

    const getTrendIcon = (trend: string) => {
        switch (trend) {
            case 'up':
                return <TrendingUp className="w-5 h-5 text-green-500" />;
            case 'down':
                return <TrendingDown className="w-5 h-5 text-red-500" />;
            default:
                return <BarChart3 className="w-5 h-5 text-gray-500" />;
        }
    };

    const getTrendColor = (trend: string) => {
        switch (trend) {
            case 'up':
                return 'text-green-600 bg-green-50';
            case 'down':
                return 'text-red-600 bg-red-50';
            default:
                return 'text-gray-600 bg-gray-50';
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header - 분석 중일 때는 숨김 */}
            <AnimatePresence>
                {!isAnalyzing && (
                    <motion.header
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        transition={{ duration: 0.3 }}
                        className="bg-white shadow-sm border-b border-gray-200"
                    >
                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                            <div className="flex items-center justify-between">
                                <Link href="/" className="text-xl font-extrabold text-gray-800">
                                    SAMSUNG <span className="font-normal text-sm block -mt-1">Newsroom</span>
                                </Link>
                                <Link
                                    href="/"
                                    className="px-4 py-2 text-sm text-gray-700 hover:text-red-600 transition font-medium"
                                >
                                    ← 메인으로
                                </Link>
                            </div>
                        </div>
                    </motion.header>
                )}
            </AnimatePresence>

            {/* Hero Section - 전체 화면으로 표시 */}
            <AnimatePresence mode="wait">
                {isAnalyzing ? (
                    <motion.section
                        key="analyzing-hero"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className="fixed inset-0 z-50 bg-gradient-to-r from-red-600 to-red-700 text-white flex items-center justify-center overflow-hidden"
                    >

                        {/* 배경 애니메이션 */}
                        <motion.div
                            className="absolute inset-0 opacity-10"
                            animate={{
                                backgroundPosition: ['0% 0%', '100% 100%'],
                            }}
                            transition={{
                                duration: 20,
                                repeat: Infinity,
                                repeatType: 'reverse',
                            }}
                            style={{
                                backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px)',
                                backgroundSize: '50px 50px',
                            }}
                        />

                        <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
                            <div className="text-center">
                                <motion.div
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.5 }}
                                    className="w-full"
                                >
                                    <motion.div
                                        className="flex items-center justify-center mb-8"
                                        animate={{ rotate: 360 }}
                                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                                    >
                                        <Loader2 className="w-20 h-20 md:w-24 md:h-24 text-white" />
                                    </motion.div>
                                    <motion.h1
                                        className="text-5xl md:text-6xl lg:text-7xl font-extrabold mb-8"
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.2 }}
                                    >
                                        트렌드를 분석하고 있습니다...
                                    </motion.h1>
                                    <motion.div
                                        className="flex flex-col md:flex-row items-center justify-center gap-4 md:gap-8 text-2xl md:text-3xl text-red-100"
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.4 }}
                                    >
                                        <motion.span
                                            animate={{ opacity: [1, 0.5, 1] }}
                                            transition={{ duration: 1.5, repeat: Infinity }}
                                            className="flex items-center gap-2"
                                        >
                                            <motion.div
                                                className="w-2 h-2 bg-white rounded-full"
                                                animate={{ scale: [1, 1.5, 1] }}
                                                transition={{ duration: 1.5, repeat: Infinity }}
                                            />
                                            데이터 수집 중
                                        </motion.span>
                                        <motion.span
                                            animate={{ opacity: [0.5, 1, 0.5] }}
                                            transition={{ duration: 1.5, repeat: Infinity, delay: 0.5 }}
                                            className="flex items-center gap-2"
                                        >
                                            <motion.div
                                                className="w-2 h-2 bg-white rounded-full"
                                                animate={{ scale: [1, 1.5, 1] }}
                                                transition={{ duration: 1.5, repeat: Infinity, delay: 0.5 }}
                                            />
                                            AI 분석 중
                                        </motion.span>
                                        <motion.span
                                            animate={{ opacity: [0.5, 0.5, 1] }}
                                            transition={{ duration: 1.5, repeat: Infinity, delay: 1 }}
                                            className="flex items-center gap-2"
                                        >
                                            <motion.div
                                                className="w-2 h-2 bg-white rounded-full"
                                                animate={{ scale: [1, 1.5, 1] }}
                                                transition={{ duration: 1.5, repeat: Infinity, delay: 1 }}
                                            />
                                            예측 생성 중
                                        </motion.span>
                                    </motion.div>
                                </motion.div>
                            </div>
                        </div>

                        {/* 스크롤 힌트 */}
                        <motion.div
                            className="absolute bottom-8 left-1/2 transform -translate-x-1/2 flex flex-col items-center gap-2 text-white/80"
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 1, duration: 0.5 }}
                        >
                            <motion.span
                                className="text-sm font-medium"
                                animate={{ opacity: [0.5, 1, 0.5] }}
                                transition={{ duration: 2, repeat: Infinity }}
                            >
                                스크롤하여 계속
                            </motion.span>
                            <motion.div
                                animate={{ y: [0, 8, 0] }}
                                transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                            >
                                <ChevronDown className="w-6 h-6" />
                            </motion.div>
                        </motion.div>
                    </motion.section>
                ) : (
                    <motion.section
                        key="normal-hero"
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, ease: "easeOut" }}
                        className="bg-gradient-to-r from-red-600 to-red-700 text-white py-16 relative overflow-hidden"
                    >
                        {/* 배경 애니메이션 */}
                        <motion.div
                            className="absolute inset-0 opacity-10"
                            animate={{
                                backgroundPosition: ['0% 0%', '100% 100%'],
                            }}
                            transition={{
                                duration: 20,
                                repeat: Infinity,
                                repeatType: 'reverse',
                            }}
                            style={{
                                backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px)',
                                backgroundSize: '50px 50px',
                            }}
                        />

                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
                            <div className="text-center">
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    transition={{ duration: 0.6, delay: 0.1 }}
                                >
                                    <motion.h1
                                        className="text-4xl md:text-5xl font-extrabold mb-4"
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.2 }}
                                    >
                                        세상의 트렌드를 분석하고 예측합니다
                                    </motion.h1>
                                    <motion.p
                                        className="text-xl md:text-2xl text-red-100 mb-8 max-w-3xl mx-auto"
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.3 }}
                                    >
                                        데이터 기반 분석을 통해 현재 트렌드를 파악하고, 미래를 예측하여
                                        더 나은 의사결정을 지원합니다.
                                    </motion.p>
                                    <motion.div
                                        className="flex items-center justify-center space-x-4 text-sm flex-wrap gap-4"
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.4 }}
                                    >
                                        <motion.div
                                            className="flex items-center space-x-2"
                                            whileHover={{ scale: 1.1 }}
                                            whileTap={{ scale: 0.95 }}
                                        >
                                            <Globe className="w-5 h-5" />
                                            <span>실시간 데이터 분석</span>
                                        </motion.div>
                                        <motion.div
                                            className="flex items-center space-x-2"
                                            whileHover={{ scale: 1.1 }}
                                            whileTap={{ scale: 0.95 }}
                                        >
                                            <BarChart3 className="w-5 h-5" />
                                            <span>AI 기반 예측</span>
                                        </motion.div>
                                        <motion.div
                                            className="flex items-center space-x-2"
                                            whileHover={{ scale: 1.1 }}
                                            whileTap={{ scale: 0.95 }}
                                        >
                                            <Calendar className="w-5 h-5" />
                                            <span>정기 업데이트</span>
                                        </motion.div>
                                    </motion.div>
                                </motion.div>
                            </div>
                        </div>
                    </motion.section>
                )}
            </AnimatePresence>

            {/* Search and Filter Section - 분석 완료 후에만 표시 */}
            <AnimatePresence>
                {!isAnalyzing && (
                    <motion.section
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 30 }}
                        transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
                        className="bg-white border-b border-gray-200 sticky top-0 z-40"
                    >
                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                            <div className="flex flex-col md:flex-row gap-4">
                                {/* Search */}
                                <div className="flex-1 relative">
                                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                                    <input
                                        type="text"
                                        placeholder="트렌드 검색..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                                    />
                                </div>
                                {/* Category Filter */}
                                <div className="flex gap-2 overflow-x-auto">
                                    {categories.map(category => (
                                        <motion.button
                                            key={category}
                                            onClick={() => setSelectedCategory(category)}
                                            initial={{ opacity: 0, scale: 0.8 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            transition={{ delay: 0.4 + categories.indexOf(category) * 0.05 }}
                                            whileHover={{ scale: 1.05 }}
                                            whileTap={{ scale: 0.95 }}
                                            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition ${selectedCategory === category
                                                ? 'bg-red-600 text-white'
                                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                                }`}
                                        >
                                            {category}
                                        </motion.button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </motion.section>
                )}
            </AnimatePresence>

            {/* Trend Cards Section - 분석 완료 후에만 표시 */}
            <AnimatePresence>
                {!isAnalyzing && (
                    <motion.div
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 30 }}
                        transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
                    >
                        <TrendCardsSection trends={filteredTrends} getTrendIcon={getTrendIcon} getTrendColor={getTrendColor} />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Predictions Section - 분석 완료 후에만 표시 */}
            <AnimatePresence>
                {!isAnalyzing && (
                    <motion.div
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 30 }}
                        transition={{ duration: 0.6, delay: 0.4, ease: "easeOut" }}
                    >
                        <PredictionsSection predictions={predictions} />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Footer - 분석 완료 후에만 표시 */}
            <AnimatePresence>
                {!isAnalyzing && (
                    <motion.footer
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        transition={{ duration: 0.5, delay: 0.6 }}
                        className="bg-gray-100 mt-12 py-8 border-t border-gray-200"
                    >
                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                            <div className="text-center text-sm text-gray-600">
                                <p>트렌드 분석 데이터는 실시간으로 업데이트됩니다.</p>
                                <p className="mt-2">마지막 업데이트: {new Date().toLocaleDateString('ko-KR')}</p>
                            </div>
                        </div>
                    </motion.footer>
                )}
            </AnimatePresence>
        </div>
    );
}

